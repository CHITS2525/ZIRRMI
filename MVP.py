# Zimbabwe Power Cut Prediction System - MVP #
# Incorporates System Design

import requests
import pandas as pd
from bs4 import BeautifulSoup
import datetime
import os
import logging
import tweepy
from io import BytesIO
from PIL import Image
import pytesseract
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
import time
import json  # Import the json module
from concurrent.futures import ThreadPoolExecutor, TimeoutError  # For better performance


# For Infobip
# from infobip_sdk.resources.sms.sms import Sms     # Import the Infobip SMS client
# from infobip_sdk.configuration import Configuration
# from infobip_sdk.api_client import ApiClient


# Logging setup
logging.basicConfig(
    filename="power_prediction.log",
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Your Twitter API credentials (Make sure you have these set up as environment variables!)
consumer_key = os.environ.get("TWITTER_CONSUMER_KEY")
consumer_secret = os.environ.get("TWITTER_CONSUMER_SECRET")
access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
access_token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")


def get_latest_zpc_generation_tweet_text_api(twitter_handle="officialZPC"):
    """Fetches the latest tweet object from the specified Twitter handle using the API."""
    try:
        auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
        auth.set_access_token(access_token, access_token_secret)
        api = tweepy.API(auth, timeout=10)  # Add timeout
        tweets = api.user_timeline(
            screen_name=twitter_handle, count=1, tweet_mode="extended"
        )
        if tweets:
            return tweets[0]  # Return the entire tweet object
        return None
    except tweepy.TweepyException as e:
        logger.warning(f"Error fetching tweet object via API: {e}")
        return None
    except TimeoutError:
        logger.warning("Timeout error while fetching tweet via API")
        return None



def get_latest_zpc_generation_tweet_text_selenium(twitter_handle="officialZPC"):
    """Fetches the latest tweet text from the specified Twitter handle using Selenium."""
    try:
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service)
        driver.set_page_load_timeout(15)  # Add timeout to page load
        zpc_twitter_url = f"https://twitter.com/{twitter_handle}"
        driver.get(zpc_twitter_url)
        time.sleep(5)  # Wait for page to load
        tweets = driver.find_elements(By.XPATH, "//article//div[@lang]")
        for tweet in tweets:
            text = tweet.text
            if "MW" in text and (
                "Kariba" in text or "Hwange" in text
            ):  # Modified condition
                logger.info("Latest Power Update Tweet Found via Selenium!")
                driver.quit()
                return text
        driver.quit()
        return None
    except Exception as e:
        logger.error(f"Error fetching tweet text via Selenium: {e}")
        if "driver" in locals():
            driver.quit()
        return None



def parse_generation_data(text):
    """Parses the extracted text to find power generation figures."""
    generation_data = {}
    lines = text.split("\n")
    for line in lines:
        if "Hwange" in line:
            parts = line.split()
            for part in parts:
                if "MW" in part:
                    generation_data["Hwange"] = part.replace(",", "")  # Remove commas
        elif "Kariba" in line:
            parts = line.split()
            for part in parts:
                if "MW" in part:
                    generation_data["Kariba"] = part.replace(",", "")  # Remove commas
        elif "IPPS" in line or "IPPs" in line:
            parts = line.split()
            for part in parts:
                if "MW" in part:
                    generation_data["IPPS"] = part.replace(",", "")  # Remove commas
        elif "TOTAL" in line:
            parts = line.split()
            for part in parts:
                if "MW" in part:
                    generation_data["TOTAL"] = part.replace(",", "")  # Remove commas
    return generation_data



class KaribaDataCollector:
    """Collects water level data from Kariba Lake"""

    def __init__(
        self,
        data_dir="data",
        zra_url="https://www.zambezira.org/hydrology/lake-levels/1000",
    ):
        self.data_dir = data_dir
        self.kariba_data_file = os.path.join(data_dir, "kariba_levels.csv")
        self.zra_url = zra_url

        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

        if os.path.exists(self.kariba_data_file):
            self.data = pd.read_csv(self.kariba_data_file)

            def parse_kariba_date(date_str):
                """Helper function to parse dates with and without time."""
                try:
                    return pd.to_datetime(
                        date_str, format="%d/%m/%Y %H:%M", dayfirst=True
                    )
                except ValueError:
                    try:
                        return pd.to_datetime(
                            date_str, format="%d/%m/%Y", dayfirst=True
                        )
                    except ValueError:
                        return pd.NaT  # Not a Time

            self.data["date"] = self.data["date"].apply(parse_kariba_date)
            self.data = self.data.dropna(
                subset=["date"]
            )  # Remove rows with dates that couldn't be parsed
        else:
            self.data = pd.DataFrame(columns=["date", "level", "percent_full"])
            self.data.to_csv(self.kariba_data_file, index=False)

    def fetch_zra_data(self):
        """Fetches the latest Kariba water level data from the ZRA website."""
        print("Attempting to fetch data from ZRA...")
        try:
            response = requests.get(self.zra_url, timeout=10)  # added timeout
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            soup = BeautifulSoup(response.content, "html.parser")

            # Updated to use the correct HTML elements
            level_element = soup.find("td", class_="row_7 col_1")
            percent_element = soup.find("td", class_="row_7 col_2")

            if level_element and percent_element:
                print("Found level and percentage elements.")
                level_text = level_element.text.strip()
                percent_text = percent_element.text.strip().replace(
                    "%", ""
                ).strip()  # Remove '%' and extra space
                print(
                    f"Level text: '{level_text}', Percentage text: '{percent_text}'"
                )
                try:
                    level = float(level_text)
                    percent_full = float(percent_text)
                    print(
                        f"Successfully converted level: {level}, percentage: {percent_full}"
                    )
                    today = datetime.date.today()
                    new_data = pd.DataFrame(
                        [
                            {
                                "date": today,
                                "level": level,
                                "percent_full": percent_full,
                            }
                        ]
                    )
                    self.data = pd.concat([self.data, new_data]).drop_duplicates(
                        subset=["date"], keep="last"
                    ).reset_index(
                        drop=True
                    )  # More efficient
                    self.data.to_csv(self.kariba_data_file, index=False)
                    logger.info(
                        f"Successfully fetched and saved ZRA data for {today}: Level={level}, Percent Full={percent_full}"
                    )
                    return True
                except ValueError:
                    logger.error(
                        f"Could not convert level or percentage to numbers: Level='{level_text}', Percent='{percent_text}'"
                    )
                    return False
            else:
                logger.warning(
                    "Could not find water level or percentage elements on the ZRA website."
                )
                print(
                    "Could not find level or percentage elements on the ZRA website."
                )
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching data from ZRA website: {e}")
            return False
        except TimeoutError:
            logger.error("Timeout error while fetching data from ZRA.")
            return False

    def get_latest_data(self):
        """
        Returns the most recent water level data, fetching from ZRA if needed.

        Returns:
            dict: A dictionary containing the latest water level data, or None if no data is available.
        """
        if self.data.empty or (
            not self.data.empty and self.data["date"].max().date() < datetime.date.today()
        ):
            self.fetch_zra_data()
        if not self.data.empty:
            return self.data.iloc[-1].to_dict()  # Get last row as dict
        return None

    def get_trend(self, days=7):
        """
        Calculate water level trends over a specified number of days.

        Args:
            days (int, optional): The number of days to calculate the trend over. Defaults to 7.

        Returns:
            float: The average change in water level per day over the specified period.
                    Returns 0 if insufficient data is available.
        """
        if len(self.data) < 2:
            return 0
        recent_data = self.data.tail(days)
        if len(recent_data) < 2:
            return 0
        first_level = recent_data.iloc[0]["level"]
        last_level = recent_data.iloc[-1]["level"]
        return (last_level - first_level) / days



class PowerOutagePrediction:
    """Generates power outage predictions based on Kariba data and ZPC tweets."""

    def __init__(self, data_dir="data"):
        """
        Initializes the PowerOutagePrediction.

        Args:
            data_dir (str, optional): The directory to store data files. Defaults to "data".
        """
        self.kariba_collector = KaribaDataCollector(data_dir)
        self.manual_data_file = os.path.join(data_dir, "power_data.txt")
        self.location_keywords = self.load_location_keywords()
        self.location_fault_data = self.load_location_fault_data()  # Load fault data
        self.executor = ThreadPoolExecutor(max_workers=3)  # Using ThreadPoolExecutor

    def load_location_keywords(self):
        """Loads location keywords from the locations.txt file."""
        keywords = []
        try:
            with open("locations.txt", "r") as f:
                for line in f:
                    keywords.append(line.strip().lower())  # Load and lowercase
        except FileNotFoundError:
            logger.error("locations.txt file not found.")
            return []
        return keywords

    def load_location_fault_data(self):
        """Loads location keywords and fault data from the locations.txt file."""
        location_data = {}
        try:
            with open("locations.txt", "r") as f:
                for line in f:
                    parts = line.strip().split(",")  # Split line by comma
                    if len(parts) == 2:
                        location = parts[0].strip().lower()
                        fault_info = parts[1].strip()
                        location_data[location] = (
                            fault_info  # Store in dictionary
                        )
                    elif len(parts) == 1:
                        location = parts[0].strip().lower()
                        location_data[location] = "No fault information available"
                    else:
                        logger.warning(
                            f"Skipping invalid line in locations.txt: {line.strip()}"
                        )
        except FileNotFoundError:
            logger.error("locations.txt file not found.")
            return {}
        return location_data

    def get_manual_generation_data(self):
        """
        Reads manual power generation data from a file.

        Returns:
            dict: A dictionary containing manual generation data,
                  or an empty dictionary if the file is not found or cannot be parsed.
        """
        manual_data = {}
        if os.path.exists(self.manual_data_file):
            try:
                with open(self.manual_data_file, "r") as f:
                    for line in f:
                        if "Kariba:" in line:
                            try:
                                manual_data["Kariba"] = line.split(":")[1].strip()
                            except IndexError:
                                logger.warning(
                                    "Could not parse Kariba data from manual file."
                                )
                        elif "Hwange:" in line:
                            try:
                                manual_data["Hwange"] = line.split(":")[1].strip()
                            except IndexError:
                                logger.warning(
                                    "Could not parse Hwange data from manual file."
                                )
                        elif "IPPS:" in line:
                            try:
                                manual_data["IPPS"] = line.split(":")[1].strip()
                            except IndexError:
                                logger.warning(
                                    "Could not parse IPPS data from manual file."
                                )
            except Exception as e:
                logger.error(f"Error reading manual power data file: {e}")
        else:
            logger.info("Manual power data file not found.")
        return manual_data

    def predict_outage_hours(self, user_location):
        """
        Predicts the number of outage hours based on Kariba data and ZPC tweets.

        Args:
            user_location (str): The user's location.

        Returns:
            int: The predicted number of outage hours.  Returns a default value if prediction fails.
        """
        kariba_data = self.kariba_collector.get_latest_data()
        manual_generation_data = self.get_manual_generation_data()
        latest_tweet = None
        zetdc_tweet_text = None  # Changed variable name
        affected_locations = []

        print("Latest Tweet Text:")
        print(zetdc_tweet_text)  # Changed variable name

        zetdc_generation_data = (
            {}
        )  # Changed variable name.  Initialize to empty dict.

        # Use manual data
        generation_data_to_use = manual_generation_data  # Changed variable name
        print("Using Manual Generation Data for Prediction:", generation_data_to_use)

        predicted_hours = 6  # Default prediction
        reason = "Unknown Reason"  # Default Reason

        if kariba_data:
            water_level = kariba_data["level"]
            if water_level < 476.0:
                predicted_hours = 17
                reason = "Low Kariba Water Levels"
            elif water_level < 477.0:
                predicted_hours = 14
                reason = "Low Kariba Water Levels"
            elif water_level < 478.0:
                predicted_hours = 10
                reason = "Low Kariba Water Levels"

        total_generation_mw = 0
        try:
            # Safely get and convert generation data, handling missing values
            kariba_mw = int(
                generation_data_to_use.get("Kariba", "0").replace("MW", "").strip()
            )
            hwange_mw = int(
                generation_data_to_use.get("Hwange", "0").replace("MW", "").strip()
            )
            ipps_mw = int(
                generation_data_to_use.get("IPPS", "0").replace("MW", "").strip()
            )
            total_generation_mw = kariba_mw + hwange_mw + ipps_mw
            print(
                f"Total Generation (Kariba: {kariba_mw}, Hwange: {hwange_mw}, IPPS: {ipps_mw}): {total_generation_mw} MW"
            )

            # Adjust prediction based on total generation compared to demand
            demand_approx_2020 = 1900
            ideal_demand = 5000
            installed_capacity = 2800

            if total_generation_mw < demand_approx_2020 * 0.7:
                predicted_hours += 4
                reason = "Insufficient Power Generation"
            elif total_generation_mw < demand_approx_2020 * 0.85:
                predicted_hours += 2
                reason = "Insufficient Power Generation"
            elif total_generation_mw > installed_capacity * 0.9:
                predicted_hours -= 1
                if predicted_hours < 0:
                    predicted_hours = 0
                    reason = "Normal Power Supply"

            # Further adjustment based on Kariba output
            if kariba_mw < 450:
                predicted_hours += 1
                reason = "Low Kariba Output"
            elif kariba_mw < 500:
                predicted_hours += 0.5
                reason = "Reduced Kariba Output"

        except Exception as e:
            logger.error(f"Error calculating total generation: {e}")
            print(f"Error calculating total generation: {e}")
            predicted_hours = 6
            reason = "Error in Calculation"

        # Check for fault information in locations.txt
        if user_location.lower() in self.location_fault_data:
            reason = self.location_fault_data[user_location.lower()]
            print(f"Fault information found in locations.txt: {reason}")

        print(f"Predicted outage hours: {predicted_hours}, Reason: {reason}")
        return predicted_hours, reason



class AlertSystem:
    """Handles sending alerts (SMS, Email, etc.)."""

    def __init__(self):
        """Initializes the AlertSystem."""
        self.prediction_engine = PowerOutagePrediction()
        # Infobip Account Information (Replace with your actual credentials)
        self.infobip_api_key = os.environ.get("Ziermi")  # Updated environment variable name
        self.infobip_base_url = "4e4688.api.infobip.com/"  # Infobip base URL - changed



    def send_alert(self, user_contact, user_location):
        """
        Sends an alert message to the user with the predicted outage hours using Infobip.

        Args:
        user_contact (str): The user's contact information (e.g., phone number).
        user_location (str): The user's location.
        """
        predicted_hours, reason = self.prediction_engine.predict_outage_hours(
            user_location
        )  # Get reason
        if predicted_hours is not None:
            message = f"Alert: Power outage expected for {predicted_hours} hours today in {user_location} due to {reason}. Prepare backup power."  # Include reason
            print(f"Sending SMS to {user_contact}: {message}")
            self.send_infobip_sms(user_contact, message)  # Send sms
        else:
            print("Could not get power outage prediction.")
            logger.error("Failed to get power outage prediction.")

    def send_infobip_sms(self, to_phone_number, message):
        """Sends an SMS message using Infobip's API directly.

        Args:
            to_phone_number (str): The recipient's phone number (including country code, e.g., 2637...).
            message (str): The text message to send.
        """
        try:
            # Infobip API endpoint for sending SMS
            url = f"https://{self.infobip_base_url}sms/2/text/advanced"  # Added https:// and corrected the f string
            print(f"Infobip URL: {url}")  # debugging
            # Set up the request headers with your API key
            headers = {
                "Authorization": f"App {self.infobip_api_key}",  #  "App YOUR_API_KEY"
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            # Construct the JSON payload with the message and recipient
            payload = {
                "messages": [
                    {
                        "destinations": [{"to": to_phone_number}],
                        "text": message,
                    }
                ]
            }

            # Convert the payload to a JSON string
            json_payload = json.dumps(payload)

            # Send the POST request to Infobip's API
            response = requests.post(url, headers=headers, data=json_payload, timeout=10)  # added timeout
            response.raise_for_status()  # Raise an exception for bad status codes

            # Parse the JSON response from Infobip
            response_json = response.json()

            if response_json and response_json.get("messages"):
                message_id = response_json["messages"][0].get("messageId")  # safer
                if message_id:
                    print(f"SMS sent successfully! Message ID: {message_id}")
                    logger.info(
                        f"SMS sent to {to_phone_number} with ID: {message_id}"
                    )
                else:
                    print("SMS sent successfully, but no message ID received.")
                    logger.warning(
                        f"SMS sent to {to_phone_number}, but no message ID received."
                    )
            else:
                print("Failed to send SMS.  Invalid or empty response.")
                logger.error(f"Failed to send SMS to {to_phone_number}: Invalid response: {response_json}")

        except requests.exceptions.RequestException as e:
            print(f"Error sending SMS: {e}")
            logger.error(f"Error sending SMS to {to_phone_number}: {e}")
        except json.JSONDecodeError:
            print("Error decoding JSON response from Infobip.")
            logger.error("Error decoding JSON response from Infobip.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            logger.error(f"An unexpected error occurred: {e}")
        except TimeoutError:
            print("Timeout error while sending SMS.")
            logger.error("Timeout error while sending SMS.")



def prediction_engine(data):
    """
    Predicts power outage based on user data using the real engine logic.
    Args:
        data (dict): User-provided data, including location.
    Returns:
        dict: A dictionary containing the message, prediction, and user data.
    """
    print("Prediction engine received:", data)

    try:
        location = data.get("location", "").strip()
        details = data.get("details", "")

        # Call the actual prediction logic
        engine = PowerOutagePrediction()
        predicted_hours, reason = engine.predict_outage_hours(location)

        prediction_text = f"Estimated outage duration in {location}: {predicted_hours} hours. Reason: {reason}"

        return {
            "message": "Outage report received!",
            "prediction": prediction_text,
            "user_data": data,
        }

    except Exception as e:
        print(f"Error in prediction engine: {e}")
        return {
            "message": "Outage report received, but prediction failed.",
            "prediction": "⚠️ Could not calculate prediction.",
            "user_data": data,
        }


def main():
    """Main function to run the prediction and alert system."""
    alert_system = AlertSystem()
    # Simulate user input (replace with actual input method in a real application)
    user_location = "Harare"  # Example location
    user_contact = "+263771234567"  # Example phone number (replace with actual user number)
    alert_system.send_alert(user_contact, user_location)



if __name__ == "__main__":
    main()
