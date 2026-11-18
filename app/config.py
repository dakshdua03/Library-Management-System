import os

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'lms-secret-key-development-minor1')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.join(BASE_DIR, "lms.db")}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MEDIA_FOLDER = os.path.join(BASE_DIR, 'media')
    COVERS_FOLDER = os.path.join(MEDIA_FOLDER, 'covers')
    PHOTOS_FOLDER = os.path.join(MEDIA_FOLDER, 'photos')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
