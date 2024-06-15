from flask import Flask, render_template, request, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField
from wtforms.validators import DataRequired, URL
from pytube import YouTube
import boto3
import os
from flask_socketio import SocketIO, emit
import eventlet
from io import BytesIO

eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

# AWS S3 configuration
s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)
bucket_name = os.getenv('AWS_S3_BUCKET_NAME')

socketio = SocketIO(app, async_mode='eventlet')

class DownloadForm(FlaskForm):
    url = StringField('YouTube URL', validators=[DataRequired(), URL()])
    quality = SelectField('Video Quality', choices=[
        ('highest', 'Highest'), 
        ('lowest', 'Lowest'), 
        ('360p', '360p'), 
        ('720p', '720p'), 
        ('1080p', '1080p')], 
        validators=[DataRequired()])

def progress_function(stream, chunk, bytes_remaining):
    total_size = stream.filesize
    bytes_downloaded = total_size - bytes_remaining
    percentage = (bytes_downloaded / total_size) * 100
    socketio.emit('progress', {'progress': percentage}, namespace='/')

@app.route('/', methods=['GET', 'POST'])
def index():
    form = DownloadForm()
    if form.validate_on_submit():
        url = form.url.data
        quality = form.quality.data
        try:
            yt = YouTube(url, on_progress_callback=progress_function)
            
            if quality == 'highest':
                stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
            elif quality == 'lowest':
                stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').asc().first()
            else:
                stream = yt.streams.filter(progressive=True, file_extension='mp4', res=quality).first()
            
            if not stream:
                return jsonify({'error': 'Selected quality is not available.'}), 400

            # Download to memory and then upload to S3
            stream_data = BytesIO()
            stream.stream_to_buffer(stream_data)
            stream_data.seek(0)

            file_key = yt.title + '.mp4'
            s3.upload_fileobj(stream_data, bucket_name, file_key)

            file_url = f"https://{bucket_name}.s3.amazonaws.com/{file_key}"

            return jsonify({'message': f'Download completed: {yt.title}', 'file_url': file_url}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return render_template('index.html', form=form)

if __name__ == '__main__':
    socketio.run(app, debug=True)
