"""
Shows basic usage of the Photos v1 API.

Creates a Photos v1 API service and prints the names and ids of the last 10 albums
the user has access to.
"""
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os.path
import pickle
import requests


def setup_api():
    # TODO: Pass in token and client_secret as parameters
    # Setup the Photo v1 API
    # From example https://developers.google.com/people/quickstart/python
    _SCOPES = ['https://www.googleapis.com/auth/photoslibrary.readonly']
    _creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as _token:
            _creds = pickle.load(_token)
    # If there are no (valid) credentials available, let the user log in.
    if not _creds or not _creds.valid:
        if _creds and _creds.expired and _creds.refresh_token:
            _creds.refresh(Request())
        else:
            _flow = InstalledAppFlow.from_client_secrets_file(
                'client_secret.json', _SCOPES)
            _creds = _flow.run_local_server()
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as _token:
            pickle.dump(_creds, _token)
    _service = build('photoslibrary', 'v1', credentials=_creds)
    return _service


def find_album(_service, _title):
    # TODO: fix error on album with no title
    # TODO: Check title is string and if blank use "Photoframe"
    # Get first set of albums
    _request = _service.albums().list(pageSize=50, fields="nextPageToken,albums(id,title)")
    _results = _request.execute()
    _albums = _results.get('albums', [])

    # Search for Photoframe. If not found then load next page of albums
    _album = None
    while _album is None:
        for _item in _albums:
            if _item['title'] == _title:
                _album = _item
                break
        else:
            _request = _service.albums().list_next(previous_request=_request, previous_response=_results)
            if _request is None:
                raise Exception('album named "photoframe" not found and no more albums to search!')
            _results = _request.execute()
            _albums = _results.get('albums', [])
    print('Found: ' + _album['title'] + ' Album')
    return _album


def list_album_contents(_service, _album_id):
    # TODO: Loop over pages
    _request = _service.mediaItems().search(body={'albumId': _album_id, 'pageSize': '10'},
                                            fields="nextPageToken,mediaItems")
    _results = _request.execute()
    _media_items = _results['mediaItems']
    return _media_items


def image_downloader(_media_items, _filename_index,):
    for _item in _media_items:
        # TODO: Cropping
        # TODO: Check if a photo or other type
        if _item['id'] in _filename_index:
            # File already exists in index
            print('Photo: ' + _item['filename'] + ' exists')
        else:
            # File needs to be downloaded
            print('Photo: ' + _item['filename'] + ' Downloading')
            _url = _item['baseUrl'] + '=w2048-h1536-c'
            _r = requests.get(_url, allow_redirects=True)
            open("photos/"+_item["filename"], 'wb').write(_r.content)
            _filename_index[_item['id']] = _item["filename"]
    return _filename_index


# Call the Photo v1 API
apiService = setup_api()

# look for album titled: 'Photoframe'
album = find_album(apiService, 'Photoframe')

# List album contents
mediaItems = list_album_contents(apiService, album['id'])

# Check if the "fileIndex" file exists and load or create. This links the file ID to the image name
# TODO: Compare index file against images in folder
# TODO: What happens if two images with same name?
if os.path.exists('fileIndex.pickle'):
    with open('fileIndex.pickle', 'rb') as indexFile:
        filenameIndex = pickle.load(indexFile)
else:
    # Does not exist, create a blank dict
    filenameIndex = {'Id': 'filename'}

# Image downloader

filenameIndex = image_downloader(mediaItems, filenameIndex)

# Save index file
with open('fileIndex.pickle', 'wb') as indexFile:
    pickle.dump(filenameIndex, indexFile)
