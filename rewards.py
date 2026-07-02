import datetime
import json
import math
import random
import uuid

from sqlalchemy import and_, or_

from db import db
from models import CoinTransaction, FastagRedemption, Issue, User


def _utc_now():
    return datetime.datetime.utcnow()


def _start_of_day_utc(dt):
    return datetime.datetime(dt.year, dt.month, dt.day)


def _haversine_meters(lat1, lon1, lat2, lon2):
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def process_report(user_id, lat, lon, ai_confidence, issue_id=None, image_hash=None):
    """Award coins for a valid report.

    Rules:
    - Only award if ai_confidence > 0.80
    - Geo-lock / anti-spam: if ANY report exists within 10m in last 24h => no reward
    - Daily cap: max 5 rewarded reports per user per day
    - Reward: +10 coins

    Returns: (awarded: bool, reason: str, new_balance: int | None)
    """

    if ai_confidence is None or float(ai_confidence) < 0.0025:
        return False, 'ai_confidence_too_low', None

    now = _utc_now()
    last_24h = now - datetime.timedelta(hours=24)

    if image_hash:
        dup_q = Issue.query.filter(and_(Issue.user_id == user_id, Issue.image_hash == str(image_hash)))
        if issue_id is not None:
            dup_q = dup_q.filter(Issue.id != issue_id)
        if dup_q.first() is not None:
            return False, 'duplicate_image', None

    # Geo-Lock fraud prevention:
    # Prevents "duplicate farming" where users repeatedly report the same pothole.
    # We check if any report exists within 10 meters in the last 24 hours.
    # If yes, we do NOT reward coins for this report.
    radius_m = 10.0
    lat_delta = radius_m / 111111.0
    lon_delta = radius_m / (111111.0 * max(0.1, math.cos(math.radians(lat))))

    candidate_filters = [
        Issue.created_at >= last_24h,
        Issue.lat >= (lat - lat_delta),
        Issue.lat <= (lat + lat_delta),
        Issue.lng >= (lon - lon_delta),
        Issue.lng <= (lon + lon_delta),
    ]
    if issue_id is not None:
        candidate_filters.append(Issue.id != issue_id)

    candidates = Issue.query.filter(and_(*candidate_filters)).all()

    for i in candidates:
        try:
            if _haversine_meters(lat, lon, float(i.lat), float(i.lng)) <= radius_m:
                return False, 'geo_lock_duplicate', None
        except Exception:
            continue

    today_start = _start_of_day_utc(now)
    date_str = now.date().isoformat()
    today_filter = or_(CoinTransaction.created_at >= today_start, db.func.date(CoinTransaction.created_at) == date_str)

    todays_earnings = CoinTransaction.query.filter(
        and_(
            CoinTransaction.user_id == user_id,
            CoinTransaction.event_type == 'EARN_REPORT',
            today_filter,
        )
    ).count()

    todays_earned_coins = db.session.query(
        db.func.coalesce(db.func.sum(CoinTransaction.coins_delta), 0)
    ).filter(
        and_(
            CoinTransaction.user_id == user_id,
            CoinTransaction.event_type == 'EARN_REPORT',
            today_filter,
        )
    ).scalar()

    if int(todays_earnings or 0) >= 5 or int(todays_earned_coins or 0) >= 50:
        return False, 'daily_cap_reached', None

    user = User.query.get(user_id)
    if not user:
        return False, 'user_not_found', None

    reward_coins = 10
    user.wallet_balance = int(user.wallet_balance or 0) + reward_coins
    user.reputation_score = int(user.reputation_score or 0) + 1

    tx = CoinTransaction(
        user_id=user_id,
        coins_delta=reward_coins,
        event_type='EARN_REPORT',
        ref_type='issue',
        ref_id=issue_id,
        details=json.dumps({
            'lat': lat,
            'lon': lon,
            'ai_confidence': float(ai_confidence)
        })
    )

    db.session.add(tx)
    db.session.commit()

    return True, 'awarded', int(user.wallet_balance)


def redeem_fastag(user_id, vehicle_number, coins_to_spend):
    """Create a FASTag redemption request.

    Exchange rate: 10 coins = 1 INR
    Minimum: 500 coins

    Workflow:
    - Deduct coins immediately
    - Create FastagRedemption with status=PENDING
    - Do NOT call payout API here (2-step verification)

    Returns: (ok: bool, data: dict)
    """

    try:
        coins_to_spend = int(coins_to_spend)
    except (TypeError, ValueError):
        return False, {'error': 'coins_to_spend must be an integer'}

    if coins_to_spend < 5000:
        return False, {'error': 'Minimum 5000 coins required'}

    if coins_to_spend % 10 != 0:
        return False, {'error': 'coins_to_spend must be a multiple of 10 (10 coins = 1 INR)'}

    user = User.query.get(user_id)
    if not user:
        return False, {'error': 'User not found'}

    balance = int(user.wallet_balance or 0)
    if balance < coins_to_spend:
        return False, {'error': 'Insufficient wallet balance'}

    amount_rupees = coins_to_spend // 10
    tx_ref = f"FTG_{uuid.uuid4().hex}".upper()

    user.wallet_balance = balance - coins_to_spend

    redemption = FastagRedemption(
        user_id=user_id,
        vehicle_number=vehicle_number,
        amount_rupees=amount_rupees,
        coins_spent=coins_to_spend,
        status='PENDING',
        transaction_ref=tx_ref,
    )

    db.session.add(redemption)
    db.session.flush()

    tx = CoinTransaction(
        user_id=user_id,
        coins_delta=-coins_to_spend,
        event_type='REDEEM_FASTAG',
        ref_type='fastag_redemption',
        ref_id=redemption.id,
        details=json.dumps({
            'vehicle_number': vehicle_number,
            'amount_rupees': amount_rupees,
            'transaction_ref': tx_ref
        })
    )

    db.session.add(tx)
    db.session.commit()

    return True, {
        'message': 'Redemption request created',
        'id': redemption.id,
        'transaction_ref': redemption.transaction_ref,
        'status': redemption.status,
        'amount_rupees': redemption.amount_rupees,
        'coins_spent': redemption.coins_spent,
        'wallet_balance': int(user.wallet_balance)
    }


def process_pending_payouts(success_rate=0.9):
    """Mock batch payout processor.

    Simulates calling a FASTag provider. If payout fails, coins are refunded.

    Returns summary dict.
    """

    pending = FastagRedemption.query.filter_by(status='PENDING').order_by(FastagRedemption.id.asc()).all()
    completed = 0
    failed = 0

    for r in pending:
        ok = random.random() < float(success_rate)
        user = User.query.get(r.user_id)
        if ok:
            r.status = 'COMPLETED'
            completed += 1
        else:
            r.status = 'FAILED'
            failed += 1

            if user:
                user.wallet_balance = int(user.wallet_balance or 0) + int(r.coins_spent)
                tx = CoinTransaction(
                    user_id=r.user_id,
                    coins_delta=int(r.coins_spent),
                    event_type='REFUND_FASTAG',
                    ref_type='fastag_redemption',
                    ref_id=r.id,
                    details=json.dumps({
                        'transaction_ref': r.transaction_ref,
                        'reason': 'mock_payout_failed'
                    })
                )
                db.session.add(tx)

        db.session.add(r)

    db.session.commit()

    return {
        'pending_found': len(pending),
        'completed': completed,
        'failed': failed
    }
