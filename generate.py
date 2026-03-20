import cv2
import os

print("Starting to generate video library...")
# הנתיב המדויק לתמונה המקורית שלך שעבדה מקודם
original_image_path = r'C:\Users\tehil\OneDrive\Desktop\Reshatot_Final\high\frame_1.png'
img = cv2.imread(original_image_path)
if img is None:
    print("Error: Could not load the original image.")
else:
    # ההגדרות של האיכויות שלנו (כמה להקטין את התמונה)
    qualities = {
        "High": 1.0,    # גודל מקורי (100%)
        "Medium": 0.5,  # חצי גודל (50%)
        "Low": 0.25     # רבע גודל (25%)
    }

    base_dir = "Video_Library"

    # מידות התמונה המקורית
    height, width = img.shape[:2]

    # עוברים על 50 פריימים
    for i in range(1, 51):
        frame_name = f"frame_{i}.jpg" # אנחנו שומרים כ-JPG כי זה קל יותר ברשת
        
        for quality_name, scale in qualities.items():
            # יצירת התיקייה אם היא לא קיימת
            folder_path = os.path.join(base_dir, quality_name)
            os.makedirs(folder_path, exist_ok=True)
            
            # חישוב הגודל החדש (לפי האיכות)
            new_width = int(width * scale)
            new_height = int(height * scale)
            
            # כיווץ התמונה
            resized_img = cv2.resize(img, (new_width, new_height))
            
            # שמירת התמונה בתיקייה המתאימה
            save_path = os.path.join(folder_path, frame_name)
            cv2.imwrite(save_path, resized_img)

    print("Success! 150 frames were generated across High, Medium, and Low folders. 🎉")