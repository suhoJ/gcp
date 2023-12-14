from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import cv2
import logging
from google.cloud import aiplatform, storage
from google.cloud.aiplatform.gapic.schema import predict
from io import BytesIO
import base64
from serpapi import GoogleSearch

# Constants
API_KEY = "376170417f71e559f654c16c14f7544cee41158ddcd29517afd06b3a2c480137"
PROJECT_ID = "568907669076"
ENDPOINT_ID = "6173592863218073600"
BUCKET_NAME = "fashion-dataset-storage"
LOCATION = "us-central1"
API_ENDPOINT = "us-central1-aiplatform.googleapis.com"

# Initialization
app = Flask(__name__)
CORS(app)
storage_client = storage.Client()
bucket = storage_client.bucket(BUCKET_NAME)

# Initialize logging
logging.basicConfig(level=logging.DEBUG)

@app.route('/')
def home():
    return "App is running!"

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def predict_image_object_detection(image_path):
    client_options = {"api_endpoint": API_ENDPOINT}
    client = aiplatform.gapic.PredictionServiceClient(client_options=client_options)
    
    encoded_content = encode_image_to_base64(image_path)
    instance = predict.instance.ImageObjectDetectionPredictionInstance(content=encoded_content).to_value()
    
    parameters = predict.params.ImageObjectDetectionPredictionParams(confidence_threshold=0.5, max_predictions=5).to_value()
    endpoint = client.endpoint_path(project=PROJECT_ID, location=LOCATION, endpoint=ENDPOINT_ID)
    
    response = client.predict(endpoint=endpoint, instances=[instance], parameters=parameters)
    return response.predictions

@app.route('/predict', methods=['POST'])
def get_prediction():
    try:
        logging.debug("Getting image from request")
        image_file = request.files['image']
    except KeyError:
        logging.error("Image not provided in the request")
        return jsonify({"error": "Image not provided"}), 400

    image_path = os.path.join('/tmp', image_file.filename)
    image_file.save(image_path)

    try:
        logging.debug("Making prediction on the image")
        predictions = predict_image_object_detection(image_path)
    except Exception as e:
        logging.error(f"Error during prediction: {e}")
        return jsonify({"error": "Failed during prediction"}), 500

    prediction_data = predictions[0]
    highest_confidence = max(prediction_data["confidences"])
    index_of_highest_confidence = prediction_data["confidences"].index(highest_confidence)
    bbox_highest_confidence = prediction_data["bboxes"][index_of_highest_confidence]
    name_highest_confidence = prediction_data["displayNames"][index_of_highest_confidence]

    most_confident_details = {
        'label': name_highest_confidence,
        'confidence': highest_confidence,
        'bounding_box': {
            'top_left': {'x': bbox_highest_confidence[0], 'y': bbox_highest_confidence[3]},
            'bottom_right': {'x': bbox_highest_confidence[1], 'y': bbox_highest_confidence[2]}
        }
    }

    image = cv2.imread(image_path)
    height, width, _ = image.shape
    top_left_x = int(most_confident_details["bounding_box"]["top_left"]["x"] * width)
    top_left_y = int(most_confident_details["bounding_box"]["top_left"]["y"] * height)
    bottom_right_x = int(most_confident_details["bounding_box"]["bottom_right"]["x"] * width)
    bottom_right_y = int(most_confident_details["bounding_box"]["bottom_right"]["y"] * height)
    roi = image[bottom_right_y:top_left_y, top_left_x:bottom_right_x]

    is_success, buffer = cv2.imencode(".jpg", roi)
    if not is_success:
        logging.error("Failed to encode the cropped image")
        return jsonify({"error": "Failed to encode the cropped image"}), 500

    byte_stream = BytesIO(buffer)

    destination_blob_name = f"cropped_images/cropped_{image_file.filename}"
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_file(byte_stream, content_type="image/jpg")

    image_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{destination_blob_name}"
    params = {
        "api_key": API_KEY,
        "engine": "google_lens",
        "url": image_url
    }
    search = GoogleSearch(params)
    serp_results = search.get_dict()

    all_visual_matches = []
    visual_matches = serp_results.get("visual_matches", [])
    for match in visual_matches:
        extracted_data = {
            "title": match.get("title", ""),
            "link": match.get("link", ""),
            "thumbnail": match.get("thumbnail", ""),
            "price": match.get("price", "")
        }
        all_visual_matches.append(extracted_data)

    blob_to_delete = bucket.blob(destination_blob_name)
    blob_to_delete.delete()

    os.remove(image_path)

    return all_visual_matches

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)

