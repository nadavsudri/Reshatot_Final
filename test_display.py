import cv2

print("Trying to load the image...")
image_path = r'C:\Users\tehil\OneDrive\Desktop\Reshatot_Final\high\frame_1.png' 
image = cv2.imread(image_path)
if image is None:
    print("Error: Could not load the image. Check the path!")
else:
    print("Success! Press any key on the image window to close it.")
    cv2.imshow('DASH Video Player Test', image)
    cv2.waitKey(0) 
    cv2.destroyAllWindows()