import os

from yoloModel import PotholeSystem

_SYSTEM = None
_SYSTEM_MODEL_PATH = None


def _default_model_path():
    return os.path.join(os.path.dirname(__file__), 'best.pt')


def get_system(model_path=None, conf_threshold=0.25):
    global _SYSTEM, _SYSTEM_MODEL_PATH

    if model_path is None:
        model_path = _default_model_path()

    if _SYSTEM is None or _SYSTEM_MODEL_PATH != model_path:
        _SYSTEM = PotholeSystem(model_path=model_path)
        _SYSTEM_MODEL_PATH = model_path

    _SYSTEM.conf_threshold = conf_threshold
    return _SYSTEM


def validate_issue_image(image_path, conf_threshold=0.25, model_path=None, min_detections=1):
    system = get_system(model_path=model_path, conf_threshold=conf_threshold)

    abs_image_path = os.path.abspath(image_path)
    abs_model_path = os.path.abspath(_SYSTEM_MODEL_PATH) if _SYSTEM_MODEL_PATH else None
    try:
        image_exists = os.path.exists(abs_image_path)
        image_size = os.path.getsize(abs_image_path) if image_exists else None
    except OSError:
        image_exists = False
        image_size = None
    try:
        model_exists = os.path.exists(abs_model_path) if abs_model_path else False
        model_size = os.path.getsize(abs_model_path) if abs_model_path and model_exists else None
    except OSError:
        model_exists = False
        model_size = None

    def run(conf):
        results = system.model(abs_image_path, conf=conf)
        detections_local = 0
        max_conf_local = 0.0
        samples_local = []
        for result in results:
            boxes = getattr(result, 'boxes', None)
            names = getattr(result, 'names', None) or getattr(system.model, 'names', None)
            try:
                detections_local += len(boxes) if boxes is not None else 0
            except Exception:
                pass
            try:
                confs = boxes.conf if boxes is not None else None
                if confs is not None and len(confs) > 0:
                    max_conf_local = max(max_conf_local, float(confs.max().item()))
            except Exception:
                pass
            try:
                if boxes is not None and getattr(boxes, 'cls', None) is not None and getattr(boxes, 'conf', None) is not None:
                    cls_list = boxes.cls.tolist()
                    conf_list = boxes.conf.tolist()
                    for i in range(min(len(cls_list), len(conf_list), 10)):
                        cls_id = int(cls_list[i])
                        conf_val = float(conf_list[i])
                        cls_name = None
                        try:
                            if isinstance(names, dict):
                                cls_name = names.get(cls_id)
                            elif isinstance(names, (list, tuple)) and 0 <= cls_id < len(names):
                                cls_name = names[cls_id]
                        except Exception:
                            cls_name = None
                        samples_local.append({
                            'cls': cls_id,
                            'name': cls_name,
                            'conf': conf_val
                        })
            except Exception:
                pass
        return detections_local, max_conf_local, samples_local

    print(f"[YOLO] validate image='{abs_image_path}' exists={image_exists} size={image_size} model='{abs_model_path}' exists={model_exists} size={model_size}")

    detections, max_conf, samples = run(conf_threshold)
    used_threshold = conf_threshold

    # Fallback: try lower threshold to reduce false rejections for clear images
    if detections < min_detections:
        fallback_threshold = 0.10
        if fallback_threshold < conf_threshold:
            det2, max2, samples2 = run(fallback_threshold)
            if det2 > detections:
                detections, max_conf, samples = det2, max2, samples2
                used_threshold = fallback_threshold

    if detections == 0:
        print(f"[YOLO] No detections for '{abs_image_path}'. max_conf={max_conf:.3f} (threshold={used_threshold})")
    else:
        print(f"[YOLO] Detections={detections} for '{abs_image_path}'. max_conf={max_conf:.3f} (threshold={used_threshold})")
        if samples:
            print(f"[YOLO] sample boxes: {samples}")

    return {
        'is_valid': detections >= min_detections,
        'detections': detections,
        'max_confidence': float(max_conf),
        'used_threshold': float(used_threshold)
    }


def is_valid_issue_image(image_path, conf_threshold=0.25, model_path=None, min_detections=1):
    info = validate_issue_image(
        image_path=image_path,
        conf_threshold=conf_threshold,
        model_path=model_path,
        min_detections=min_detections,
    )
    return bool(info['is_valid']), int(info['detections'])
