%reset -f

import torch
import cv2
import numpy as np
import skfuzzy as fuzz  # Correct import for scikit-fuzzy

# Load the MiDaS model for depth estimation
model_type = "DPT_Large"  # or "DPT_Hybrid" for a lighter model
midas = torch.hub.load("intel-isl/MiDaS", model_type)

# Load the transform for MiDaS model
transform = torch.hub.load("intel-isl/MiDaS", "transforms").dpt_transform

video_path = 'tst.mp4'  
cap = cv2.VideoCapture(video_path)

# Check if the video opened successfully
if not cap.isOpened():
    print("Error: Could not open video.")
    exit()

# Get video properties
frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

# Set up video writer to save the output enhanced depth video
output_width, output_height = 256, 256  # Decreased dimensions for faster processing
fourcc = cv2.VideoWriter_fourcc(*'XVID')  # Codec for output video
output_video = cv2.VideoWriter('ANFIS_Video_Depth_Map.avi', fourcc, fps, (output_width, output_height), False)

# A simple ANFIS model
class SimpleANFIS:
    def predict(self, input_depth):
        # A dummy ANFIS model that adjusts depth slightly based on fuzzy logic rules
        adjusted_depth = input_depth * 0.9 + 0.1  # Adjust depth by some factor
        return adjusted_depth

anfis_model = SimpleANFIS()

# Define fuzzy membership functions using skfuzzy
x_depth = np.linspace(0, 1, 256)  # Depth values between 0 and 1

# Create fuzzy membership functions (Low, Medium, High depth)
depth_low = fuzz.trimf(x_depth, [0, 0, 0.5])  # Low depth
depth_medium = fuzz.trimf(x_depth, [0, 0.5, 1])  # Medium depth
depth_high = fuzz.trimf(x_depth, [0.5, 1, 1])  # High depth

# Process the video frame by frame
frame_count = 0
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    frame_count += 1
    print(f"Processing frame {frame_count}/{total_frames}")

    # Pre-process the frame (convert to RGB and resize to smaller input size)
    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img_rgb_resized = cv2.resize(img_rgb, (256, 256))  # Adjust size for faster processing

    # Apply the MiDaS transform (resize and normalize the image)
    input_batch = transform(img_rgb_resized).unsqueeze(0)

    # Ensure input tensor has the correct dimensions
    if len(input_batch.shape) == 5:
        input_batch = input_batch.squeeze(1)

    # Move model and tensor to GPU if available
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    midas.to(device)
    input_batch = input_batch.to(device)

    # Perform inference (depth estimation)
    with torch.no_grad():
        prediction = midas(input_batch)

    # Convert the prediction to a depth map
    depth_map = prediction.squeeze().cpu().numpy()

    # Normalize the depth map for further processing
    depth_map_normalized = cv2.normalize(depth_map, None, 0, 1, norm_type=cv2.NORM_MINMAX)

    # Apply the ANFIS model to the depth map
    depth_map_enhanced = np.zeros_like(depth_map_normalized)
    for i in range(depth_map_normalized.shape[0]):
        for j in range(depth_map_normalized.shape[1]):
            # Get the depth value
            depth_value = depth_map_normalized[i, j]
            
            # Use ANFIS model to predict the enhanced depth
            enhanced_value = anfis_model.predict(depth_value)
            depth_map_enhanced[i, j] = enhanced_value

    # Normalize the enhanced depth map for saving
    depth_map_enhanced = cv2.normalize(depth_map_enhanced, None, 0, 255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U)

    # Resize the enhanced depth map to match the output video size
    depth_map_enhanced_resized = cv2.resize(depth_map_enhanced, (output_width, output_height))

    # Save the enhanced depth map to the video
    output_video.write(depth_map_enhanced_resized)

cap.release()
output_video.release()
