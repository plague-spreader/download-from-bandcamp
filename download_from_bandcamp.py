#! /usr/bin/env python
#######################

import os
import argparse
import sys
import json
import re
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import urllib
from lxml import html
import eyed3

def requests_retry_session(
		retries=3,
		backoff_factor=0.3,
		status_forcelist=(500, 502, 504),
		session=None,
		):
	session = session or requests.Session()
	retry = Retry(
		total=retries,
		read=retries,
		connect=retries,
		backoff_factor=backoff_factor,
		status_forcelist=status_forcelist,
	)
	adapter = HTTPAdapter(max_retries=retry)
	session.mount('http://', adapter)
	session.mount('https://', adapter)
	return session

class NotBandcampUrl(Exception):
	def __init__(self, url):
		self.url = url

class DontWantToDownload(Exception):
	# actually not an exception
	pass

def get_html(url):
	ret = requests_retry_session().get(url).text
	if 'var siteroot = "http://bandcamp.com";' not in ret:
		# hopefully this is a sound method for checking if <url> is a valid
		# bandcamp url ...
		raise NotBandcampUrl(url)
	return ret

def get_info(url):
	html_content = get_html(url)
	album_art = html.fromstring(html_content)
	album_art = album_art.xpath('//div[@id="tralbumArt"]/a/@href')[0]
	html_lines = html_content.split('\n')
	del html_content
	ind_start = html_lines.index('var TralbumData = {')
	ind_end = html_lines[ind_start:]
	ind_end = ind_start + ind_end.index('};')
	data = html_lines[ind_start:ind_end+1]
	del html_lines
	data[0] = '{'
	i = 1
	while i < len(data):
		if data[i][4:6] == '//' or data[i][4:13] == 'item_type' \
or data[i][4:7] == 'url':
			del data[i]
			continue
		ci = data[i].find(':')
		data[i] = '    "{}": {}'.format(data[i][4:ci], data[i][ci+1:])
		i += 1
	data[-1] = '}'
	data = "".join(data)
	data = json.loads(data)
	trackinfo = data['trackinfo']
	tracks = []
	download_even_if_missing = False
	for the_track in trackinfo:
		if not the_track["file"]:
			if not download_even_if_missing:
				choice_made = False
				while not choice_made:
					s_choice = input("\nNot all tracks are available for \
download. Do you still want to download what's there (y or n)? ")
					choice_made = s_choice in "yn"
					if not choice_made:
						print("Just enter a lowercase y or n")
				download_even_if_missing = s_choice == "y"
				if not download_even_if_missing:
					raise DontWantToDownload()
			tracks.append((the_track["title"], None))
		else:
			tracks.append((the_track["title"], the_track["file"]["mp3-128"]))
	return {
	'album': data['current']['title'],
	'album_art': album_art,
	'artist': data['artist'],
	'tracks': tracks
	}

def download(url, filename):
	with open(filename, 'wb') as f:
		ret = requests_retry_session().get(url).content
		f.write(ret)
	return ret

def download_single_album(url):
	print('Downloading album from URL "{}"'.format(url))
	print("Retrieving info from bandcamp... ", end='', flush=True)
	info = get_info(url)
	print("Done.")
	if not info["tracks"]:
		print('The bandcamp URL "{}" does not contain any MP3s'.format(url))
		return
	album_dir = info["album"].replace("/", "-")
	os.mkdir(album_dir)
	os.chdir(album_dir)
	print("Downloading album art... ", end='', flush=True)
	image_data = download(info['album_art'], 'Cover.jpg')
	print("Done.")
	lt = len(str(len(info['tracks'])))
	# ^ number of digits of len(info['tracks'])
	i = 1
	filenames = []
	for t in info['tracks']:
		num = str(i).zfill(lt)
		print("\rDownloading track [{}/{}]".format(
		num, len(info['tracks'])
		), end='', flush=True)
		if t[1]:
			track_filename = t[0].lower().replace(' ', '_')
			track_filename = '{} - {}.mp3'.format(num, track_filename)
			track_filename = track_filename.replace("/", "\\")
			download(t[1], track_filename)
			id3 = eyed3.load(track_filename)
			if not id3.tag:
				id3.initTag()
				id3.tag.artist = info["artist"]
				id3.tag.album = info["album"]
				id3.tag.album_artist = info["artist"]
				id3.tag.title = t[0]
				id3.tag.track_num = i
				id3.tag.images.set(3, image_data, "image/jpeg")
				id3.tag.save()
			filenames.append(track_filename)
		i += 1
	print('\r', end='', flush=True)
	print(' '*(21+2*lt), end='', flush=True)
	print("\rTracks downloaded.", flush=True)
	print("Enjoy your album.", flush=True)
	os.chdir("..")

def download_from_container(url):
	print('Downloading albums from container URL "{}"'.format(url))
	directory = url[url.index("://")+3:]
	try:
		directory = directory[:directory.rindex(".bandcamp.com")]
	except ValueError:
		# apparently not all bandcamp links has .bandcamp.com
		directory = directory[:directory.index("/music")]
	os.mkdir(directory)
	os.chdir(directory)
	html_content = html.fromstring(get_html(url))
	hrefs = \
html_content.xpath("//li[contains(@class, 'music-grid-item')]/a/@href")
	base_url = url[:url.rindex("/")]
	for href in hrefs:
		download_single_album(base_url + href)
	os.chdir("..")

def main(args):
	for url in args.urls:
		try:
			if url.endswith("/music"):
				download_from_container(url)
			else:
				download_single_album(url)
		except NotBandcampUrl as e:
			print('"{}" is not a valid Bandcamp URL.'.format(e.url))
		except DontWantToDownload:
			print("Download aborted as requested.")

if __name__ == '__main__':
	ap = argparse.ArgumentParser()
	ap.add_argument("urls", nargs="+")
	main(ap.parse_args())
