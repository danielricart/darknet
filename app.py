import os
# We'll render HTML templates and access data sent by POST
# using the request object from flask. Redirect and url_for
# will be used to redirect the user once the upload is done
# and send_from_directory will help us to send/show on the
# browser the file that the user just uploaded
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, Markup, jsonify
from werkzeug import secure_filename
import logging
import subprocess
import cv2

# Initialize the Flask application
app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

# Size limit
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024
# This is the path to the upload directory
app.config['UPLOAD_FOLDER'] = 'uploads/'
# These are the extension that we are accepting to be uploaded
app.config['ALLOWED_EXTENSIONS'] = set(['png', 'jpg', 'jpeg', 'bmp'])
# Result folder
app.config['OUTPUT_FOLDER'] = 'output/'

def adaptive_resize(filename, max_size=640):
    img = cv2.imread(filename, 1)
    h, w, _ = img.shape
    ratio1 = float(max_size) / h
    ratio2 = float(max_size) / w
    ratio = min(ratio1, ratio2)
    if ratio >= 1:
        return
    img = cv2.resize(img, (int(ratio*w), int(ratio*h)))
    cv2.imwrite(filename, img)
    

# For a given file, return whether it's an allowed type or not
def allowed_file(filename):
    return '.' in filename and \
           (filename.rsplit('.', 1)[1] in app.config['ALLOWED_EXTENSIONS'] or
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS'])

# This route will show a form to perform an AJAX request
# jQuery is loaded to execute the request and update the
# value of the operation
@app.route('/')
def index():
    return render_template('index.html')


# Route that will process the file upload
@app.route('/upload', methods=['POST'])
def upload():
    # Get the name of the uploaded file
    file = request.files['file']
    # Check if the file is one of the allowed types/extensions
    if file and allowed_file(file.filename):
        # Make the filename safe, remove unsupported chars
        filename = secure_filename(file.filename)
        # Move the file form the temporal folder to
        # the upload folder we setup
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        try:
            adaptive_resize(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        except:
            pass
        # Redirect the user to the uploaded_file route, whicuploadh
        # will basicaly show on the browser the uploaded file

        output_filename = "".join([app.config['OUTPUT_FOLDER'], filename.split(".")[0]])
        cmd = "./darknet detect cfg/yolov3.cfg yolov3.weights %s%s -out %s" % (app.config['UPLOAD_FOLDER'], filename, output_filename)
        try:
            stdout_result = subprocess.check_output(cmd, shell=True)
            info = stdout_result.decode('utf-8').split(':')[1:]
            info = ''.join(info)
            text = ""
            for line in info.split('\n'):
                text += Markup.escape(line) + Markup('<br />')
            
            if request.accept_mimetypes.accept_json:
                logging.debug("requested json")
                return jsonify(parse_output(info))
            
            return render_template('result.html', filename=os.path.join(app.config['OUTPUT_FOLDER'], os.path.basename(filename)), result_text=text)
        except Exception as ex:
            print("error ocurred: %s", ex)
            return render_template('result.html', filename=os.path.join(app.config['UPLOAD_FOLDER'], filename), result_text="Unexpected error occured, terminate detection.")
        #return redirect(url_for('uploaded_file', filename=filename))
    return "Invalid file or format"


def parse_output(output):
    result = []
    out_lines = output.splitlines()
    if 'Predicted' not in out_lines[0]:
        raise Exception("Error predicting content")
    if len(out_lines) > 1:
        for line in out_lines[1:]:
            result.append(parse_prediction(line))
    return result


def parse_prediction(prediction):
    parts = prediction.split(" - ")
    logging.debug(parts) 
    item = parts[0].split(" ")[0]
    logging.debug(item)
    probability = parts[0].split(" ")[1]
    logging.debug(probability)
    bounding_box = parts[1].split(" ")[1:]
    logging.debug(bounding_box)
    item_size = parts[2].split(" ")[1]
    logging.debug(item_size)
    prediction = {
        "Object": item,
        "Confidence": probability,
        "Geometry": {
            "BoundingBox": { 
                "Top": bounding_box[0].split(",")[0],
                "Left": bounding_box[0].split(",")[1],
                "Bottom": bounding_box[1].split(",")[0],
                "Right": bounding_box[1].split(",")[1]
            },
            "Size": item_size
        }
    }
    
    return prediction

# This route is expecting a parameter containing the name
# of a file. Then it will locate that file on the upload
# directory and show it on the browser,decode('utf-8') so if the user uploads
# an image, that image is going to be show after the upload
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'],
                               filename)

@app.route('/output/<filename>')
def output_file(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'],
                               filename)

@app.route('/<filename>')
def root_file(filename):
    return send_from_directory('./', filename)

if __name__ == '__main__':
    app.run(
        host="0.0.0.0",
        port=int("8080"),
        debug=False
    )

