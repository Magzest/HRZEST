import face_recognition
import os
import pickle

known_faces = []
known_names = []

dataset_path = "dataset"

for file in os.listdir(dataset_path):
    img = face_recognition.load_image_file(f"{dataset_path}/{file}")
    encodings = face_recognition.face_encodings(img)

    if encodings:
        encoding = encodings[0]
        known_faces.append(encoding)
        known_names.append(file.split(".")[0])

data = {"encodings": known_faces, "names": known_names}

with open("faces.pickle", "wb") as f:
    pickle.dump(data, f)

print("Face training completed")