#!/usr/bin/env python3
"""
Shows basic usage of the Photos v1 API.

Creates a Photos v1 API service and downloads the images in the "Photoframe Album"
"""
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
import os.path
import pickle
import requests
import logging

logging.basicConfig(level=logging.INFO)

# Directory to store images
# TODO: Move to conf file
imagesDir = "/Images/"
albumTitle = "Photoframe"
projectDir = "/home/lawrence/sync-album-from-google-photos/"

def setup_api():
    # TODO: Pass in token and client_secret as parameters
    # Setup the Photo v1 API
    # From example https://developers.google.com/people/quickstart/python
    # How to use: Follow link in console and copy auth code from final URL
    # Input: None
    # Output: _service: apiService for access to photos
    _SCOPES = ['https://www.googleapis.com/auth/photoslibrary.readonly']
    _creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.isfile(os.path.join(projectDir, 'token.pickle')):
        with open(projectDir + 'token.pickle', 'rb') as _token:
            _creds = pickle.load(_token)
    # If there are no (valid) credentials available, let the user log in.
    if not _creds or not _creds.valid:
        if _creds and _creds.expired and _creds.refresh_token:
            _creds.refresh(Request())
        else:
            _flow = Flow.from_client_secrets_file(
                projectDir + 'client_secret.json', _SCOPES, redirect_uri='http://localhost:8080/')
            _auth_url, _ = _flow.authorization_url(prompt='consent')
            # Tell the user to go to the authorization URL.
            print('Please go to this URL: {}'.format(_auth_url))
            # The user will get an authorization code. This code is used to get the
            # access token.
            code = input('Enter the authorization code: ')
            _flow.fetch_token(code=code)
            _creds = _flow.credentials
        # Save the credentials for the next run
        with open(projectDir + 'token.pickle', 'wb') as _token:
            pickle.dump(_creds, _token)
    _service = build('photoslibrary', 'v1', credentials=_creds)
    return _service


def find_album(_service, _title):
    # Finds album with the provided title
    # In: _service: Created using the googleapiclient
    #     _title: title of the album of interest (string)
    # Out: _album: Photos api album object
    #             https://developers.google.com/photos/library/reference/rest/v1/albums/list#response-body
    # TODO: fix error on album with no title
    # TODO: Check title is string and if blank use "Photoframe"
    # TODO: Alternative to exception due to album not found

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
    logging.info('Found: ' + _album['title'] + ' Album')
    return _album


def list_album_contents(_service, _album_id):
    # Lists all of the items in an album
    # In: _service: apiService for access to photos
    #     _album_id: id of album to find contents of (string)
    # Out: _media_items: list of media items in album.
    #      https://developers.google.com/photos/library/reference/rest/v1/mediaItems#resource-mediaitem

    _request = _service.mediaItems().search(body={'albumId': _album_id, 'pageSize': '100'},
                                            fields="nextPageToken,mediaItems")
    _media_items = []
    while _request is not None:
        _results = _request.execute()
        _media_items.extend(_results['mediaItems'])
        _request = _service.albums().list_next(previous_request=_request, previous_response=_results)

    return _media_items


def delete_removed_images(_filename_index, __media_items, _images_dir):
    # Check for deletions in Photos Album
    # If item is in _filename_index but not in __media_items, delete
    _found = 0
    _idToDelete = []
    for _idInDir in _filename_index:
        for _mediaItemInAlbum in __media_items:
            if _idInDir == _mediaItemInAlbum['id']:
                _found = 1
        if not _found:
            _idToDelete.append(_idInDir)
        _found = 0

    for _id in _idToDelete:
        logging.info("Delete: " + _filename_index.get(_id))
        if os.path.exists(_images_dir + _filename_index.get(_id)):
            os.remove(_images_dir + _filename_index.get(_id))
        if os.path.exists(_images_dir + "Thumbnails/" + _filename_index.get(_id)):
            os.remove(_images_dir + "Thumbnails/" + _filename_index.get(_id))
        del _filename_index[_id]

    return _filename_index


def image_downloader(_media_items, _filename_index, _directory):
    # Downloads all of the mediaitems in list, saves to _directory
    # In: _media_items: list of media items in album.
    #                   https://developers.google.com/photos/library/reference/rest/v1/mediaItems#resource-mediaitem
    #     _filename_index: Dictionary of photo id and filenames, aim is to list the currently downloaded images
    #                      Is auto-generated if empty
    #     _directory: Location to store photos, must end in "/"
    # Out: _filename_index:  Dictionary of photo id and filenames, listing the currently downloaded images

    for _item in _media_items:
        if _item['id'] in _filename_index:
            # File already exists in index
            logging.info('Keep: ' + _item['filename'])
        else:
            # File needs to be downloaded
            logging.info('Download: ' + _item['filename'])

            # Check if photo of same name exists
            if os.path.exists(_directory + _item["filename"]):
                logging.warning("Duplicate exists for " + _item["filename"])
                _filename, _file_extension = os.path.splitext(_item["filename"])
                _filename = _filename + '_2'
                _item["filename"] = _filename + _file_extension

            # Download Media
            if 'photo' in _item['mediaMetadata']:
                # Request photo
                _url = _item['baseUrl'] + '=w2048-h1536-c'
                _r = requests.get(_url, allow_redirects=True)
                # Save photo
                open(os.path.join(_directory, _item["filename"]), 'wb').write(_r.content)
            if 'video' in _item['mediaMetadata']:
                # TODO: Check Video is ready
                # Request video
                _url = _item['baseUrl'] + '=dv'
                _r = requests.get(_url, allow_redirects=True)
                # Save video
                open(os.path.join(_directory, _item["filename"]), 'wb').write(_r.content)

            # Request thumbnail
            _url = _item['baseUrl'] + '=w400-h400'
            _r = requests.get(_url, allow_redirects=True)
            # Save Thumbnail
            open(os.path.join(_directory, "Thumbnails", _item["filename"]), 'wb').write(_r.content)
            # Add image to downloaded list
            _filename_index[_item['id']] = _item["filename"]
    return _filename_index


# Call the Photo v1 API to setup a service for use later
apiService = setup_api()
# look for album titled: 'Photoframe'
album = find_album(apiService, albumTitle)
# Get the contents of the album
mediaItems = list_album_contents(apiService, album['id'])
# TODO: Make thumbnails folder if it does not exist

# Check if the "fileIndex" file exists and load or create. This links the file ID to the image name
if os.path.exists(projectDir + 'fileIndex.pickle'):
    with open(projectDir + 'fileIndex.pickle', 'rb') as indexFile:
        filenameIndex = pickle.load(indexFile)
else:
    # Does not exist, create a blank dict
    filenameIndex = {}

# Delete images removed from album
filenameIndex = delete_removed_images(filenameIndex, mediaItems, imagesDir)

# Download the images
filenameIndex = image_downloader(mediaItems, filenameIndex, imagesDir)

# Save the "filenameIndex" file
with open(projectDir + 'fileIndex.pickle', 'wb') as indexFile:
    pickle.dump(filenameIndex, indexFile)
