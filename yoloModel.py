import cv2
from ultralytics import YOLO
import time

class PotholeSystem:
    def __init__(self, model_path='best.pt'):
        """
        Initialize the AI Model.
        In a real scenario, change 'yolov8n.pt' to your trained pothole model (e.g., 'pothole_v1.pt')
        """
        print(f"Loading AI Model: {model_path}...")
        self.model = YOLO(model_path) 
        # confident_threshold: Only report if AI is more than 50% sure
        self.conf_threshold = 0.5 

    def process_image(self, image_path):
        """
        Simulates the User App: Takes a photo and detects issues.
        """
        print(f"\n--- Processing Community Image: {image_path} ---")
        
        # Run inference
        results = self.model(image_path)
        
        # Visualize the results
        for result in results:
            # result.boxes contains the detection data
            print(f"Detected {len(result.boxes)} object(s).")
            
            # Save the annotated image (image with boxes drawn)
            output_filename = "output_" + image_path
            result.save(filename=output_filename)
            print(f"Report image saved as: {output_filename}")
            
            # Here you would add logic to upload to your database
            # if len(result.boxes) > 0: upload_to_db(lat, long, output_filename)

    def process_cctv_stream(self, video_path):
        """
        Simulates the Government CCTV: Reads video, checks frames periodically.
        """
        print(f"\n--- Processing CCTV Stream: {video_path} ---")
        cap = cv2.VideoCapture(video_path)
        
        frame_rate = 30 # Assuming 30 FPS
        process_every_n_seconds = 2 # Check for potholes every 2 seconds
        frame_interval = frame_rate * process_every_n_seconds
        
        frame_count = 0
        
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                break

            # Optimization: Only run AI on specific frames to save resources
            if frame_count % frame_interval == 0:
                print(f"Scanning frame {frame_count} for potholes...")
                
                # Run YOLO on this specific frame
                results = self.model(frame, conf=self.conf_threshold)
                
                # Check if anything was detected in this frame
                for result in results:
                    if len(result.boxes) > 0:
                        print(f" ALERT! Potential road damage detected at frame {frame_count}")
                        # In a real app, you would capture the timestamp here
                        
                        # Show the frame to us for debugging
                        annotated_frame = result.plot()
                        cv2.imshow("CCTV Monitoring - AI View", annotated_frame)
            
            frame_count += 1
            
            # Press 'q' to quit the CCTV view
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

# --- Execution ---
if __name__ == "__main__":
    # Initialize the system
    system = PotholeSystem()

    # MODE 1: Test with a single image (Make sure you have an image named 'test_road.jpg')
    system.process_image("tesy_road.jpg")

    # MODE 2: Test with a video file (Make sure you have a video named 'traffic.mp4')
    # To test this, uncomment the line below and ensure you have a video file.
    # system.process_cctv_stream("traffic.mp4")
    
    print("\nSystem ready. Uncomment Mode 1 or Mode 2 in the code to run.")