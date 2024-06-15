import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, jsonify, send_file
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField
from wtforms.validators import DataRequired, URL
from pytube import YouTube
import os
from io import BytesIO
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

# Use the user's Downloads directory
home_directory = os.path.expanduser('~')
downloads_path = os.path.join(home_directory, 'Downloads')

if not os.path.exists(downloads_path):
    os.makedirs(downloads_path)

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

            # Download to memory
            stream_data = BytesIO()
            stream.stream_to_buffer(stream_data)
            stream_data.seek(0)

            return send_file(
                stream_data, 
                as_attachment=True, 
                download_name=f"{yt.title}.mp4",
                mimetype="video/mp4"
            )
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return render_template('index.html', form=form)

if __name__ == '__main__':
    socketio.run(app, debug=True)
