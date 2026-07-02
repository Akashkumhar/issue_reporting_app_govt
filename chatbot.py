import os
import google.generativeai as genai
import logging
from google.api_core import exceptions as google_exceptions

# It's recommended to load secrets from environment variables
# rather than hardcoding them in the source code.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def send_message_to_gemini(user_id, message):
    """
    Sends a message to the Gemini API and returns the response.

    Args:
        user_id (int): The ID of the user sending the message.
        message (str): The message content.

    Returns:
        str: The response from the Gemini API.
    """
    try:
        if not GEMINI_API_KEY:
            return "Error: GEMINI_API_KEY is not configured."
        # Use 'gemini-1.5-pro-latest' as it's the recommended stable model and
        # is more likely to be compatible across different client library versions.
        model = genai.GenerativeModel('gemini-1.5-pro-latest')
        response = model.generate_content(message)
        
        # The 'response.text' accessor will raise a ValueError if the
        # response was blocked for safety reasons. We handle that here.
        try:
            return response.text
        except ValueError:
            logging.warning(f"Gemini response blocked for user {user_id}. Feedback: {response.prompt_feedback}")
            return "I am unable to provide a response to that. Please try a different message."

    except google_exceptions.PermissionDenied as e:
        logging.error(f"Gemini API Permission Denied for user {user_id}: {e}")
        return "API access denied. Please ensure the Generative Language API is enabled in your Google Cloud project and that billing is active."
    except google_exceptions.InvalidArgument as e:
        logging.error(f"Gemini API Invalid Argument for user {user_id}: {e}")
        return "There was an issue with the API request, which could be related to an invalid API key. Please check your configuration."
    except google_exceptions.ResourceExhausted as e:
        logging.warning(f"Gemini API quota exceeded for user {user_id}: {e}")
        return "The chatbot is currently experiencing high traffic. Please try again in a few moments."
    except Exception as e:
        # Log the full error for easier debugging
        logging.error(f"Gemini API error for user {user_id}: {e}")
        return f"Error communicating with the Gemini API. Please check the server logs."
