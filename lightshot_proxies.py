import requests
import urllib.request
from bs4 import BeautifulSoup
from lightshot_logger import get_logger
import os
import time
import psutil
from multiprocessing.dummy import Pool as ThreadPool
from util_functions import safe_open
from pathlib import Path

LOGGER = get_logger()

IMAGE_CONFIG = {'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'}


class ImageDownloader(object):
    user_agent = IMAGE_CONFIG['user_agent']

    def __init__(self, queue, proxy_handler_instance=None, max_requests_per_proxy=250, stop_at=None, max_threads=8,
                 *args, **kwargs):
        self.proxy_handler = proxy_handler_instance
        self.max_threads = max_threads

        self.max_requests_per_proxy = max_requests_per_proxy
        self._max_requests_increment = self.max_requests_per_proxy

        self.queue = queue
        self.downloaded_list = get_downloaded_list()

        self.requests_sent = int()
        self.stop_at = stop_at

        self.url = str()
        self.downloaded = False

        self.do_delete = False
        self.move_to_archive = False
        self.done = False

        self.deleted = False
        self.archived = False
        self.path = None
        self.download_count = int()

        self.image_download_queue = list()
        self.url_queue = list()

    @property
    def url(self):
        return self._url

    @url.setter
    def url(self, val):
        if val != '':
            LOGGER.debug('URL changed: {}'.format(val))
        self._url = val

    @staticmethod
    def log_memory_usage():
        process = psutil.Process(os.getpid())
        x = process.memory_info()
        memory_used = x.rss / 1000000000
        LOGGER.debug('Memory Usage: {}'.format(memory_used))

    def reset_flags(self):
        self.downloaded = False

        self.do_delete = False
        self.move_to_archive = False
        self.done = False

        self.deleted = False

        self.image_download_queue = list()
        self.url_queue = list()

    def get_next_url(self, last_url):
        self.url = self.queue.get()
        self.done = self.queue.done


    def update_proxies(self):
        if self.requests_sent >= self.max_requests_per_proxy:
            self.max_requests_per_proxy += self._max_requests_increment + (
                    self.requests_sent - self.max_requests_per_proxy)
            proxy_handler.install_next_proxy()
            self.log_memory_usage()

    def run(self):
        while True:
            self.update_proxies()
            self.reset_flags()
            t = time.perf_counter()
            self.perform_download()
            LOGGER.debug('Time for download loop: {}'.format(time.perf_counter() - t))

    def perform_download(self):
        last_url = str()
        while not self.done:
            if not self.downloaded:
                self.get_next_url(last_url)
                self.download()

            if self.do_delete:
                self.delete()

            self.done = self.deleted or self.downloaded
            if self.stop_at is not None:
                self.done = self.done or self.download_count >= self.stop_at

            if self.done:
                self.downloaded_list.append(self.url)

            last_url = self.url

    def check_already_downloaded(self):
        if self.url in self.downloaded_list:
            LOGGER.debug('Image already downloaded: {}'.format(self.url))
            return True
        return False

    def send_html_request(self):

        LOGGER.debug('Starting to download {}'.format(self.url))

        full_url = "https://prnt.sc/{}".format(self.url)
        request = urllib.request.Request(full_url, headers={'User-Agent': self.user_agent, 'referrer': 'https://www.google.com', 'X-Forwarded-For': ''})
        html = None

        try:
            response = urllib.request.urlopen(request)
        except:
            LOGGER.debug('Request of {} failed, trying other proxy'.format(full_url))
            for i in range(self.proxy_handler.count):
                LOGGER.debug('Request of {} failed, trying other proxy'.format(full_url))
                opener = self.proxy_handler.return_opener()
                try:
                    response = opener.open(request)
                except:
                    LOGGER.debug('Request of {} failed, trying other proxy'.format(full_url))


        if response.status == 200:
            self.requests_sent += 1
            html = response.read()

        LOGGER.debug('Response Code: {}, URL: '.format(response.status, response.url))

        return html

    def get_image_tags(self):
        html = self.send_html_request()
        soup = BeautifulSoup(html, 'html.parser')
        image_tags = soup.find_all('img')
        return image_tags

    def parse_new_urls(self, new_urls):
        if len(new_urls) == 0:
            LOGGER.debug('Could not find any images in current URL ({})'.format(self.url))

        elif len(new_urls) == 1:
            LOGGER.debug('Found {} new URLs: {}'.format(len(new_urls), new_urls))
            self.image_download_queue += new_urls
            self.url_queue.append(self.url)

    def start_threads(self, request_list, size=8):
        pool = ThreadPool(size)
        opener = self.proxy_handler.return_opener()
        responses = pool.map(opener.open, request_list)
        pool.close()
        pool.join()
        return responses

    def download(self):

        # This method is called until enough image URLS are scraped to start a threaded download of them

        if self.check_already_downloaded():
            return self.downloaded

        image_tags = self.get_image_tags()

        new_urls = [image_tag['src'] for image_tag in image_tags if
                    self.url not in image_tag['src'] and 'footer' not in image_tag['src'] and not str(
                        image_tag['src']).startswith('//')]

        self.parse_new_urls(new_urls)

        if self.is_image_queue_full():
            self.download_image_loop()

        return self.downloaded

    def is_image_queue_full(self):
        return len(self.image_download_queue) >= self.max_threads

    def download_image_loop(self):

        started = time.perf_counter()

        images_for_thread_pool = self.image_download_queue[-self.max_threads::]
        url_queue_copy = self.url_queue.copy()

        LOGGER.debug('Starting {} new download threads'.format(self.max_threads))

        request_list = [urllib.request.Request(image_url, headers={'User-Agent': self.user_agent}) for image_url in
                        images_for_thread_pool]

        responses = self.start_threads(request_list, size=self.max_threads)
        self.requests_sent += self.max_threads

        LOGGER.debug('8 images successfully downloaded, Beginning to write images to disk')

        self.write_images(responses, url_queue_copy)

        LOGGER.error('Time taken for download: {}'.format(time.perf_counter() - started))
        LOGGER.error('Downloaded a total of {} files'.format(self.download_count))

    def write_images(self, response_list, url_queue):
        index = 0
        for response in response_list:
            path = 'data/img/{}{}'.format(url_queue[index], os.path.splitext(response.url)[1])
            self._write_image_from_response(response.read(), path)
            index += 1

        self.downloaded = True

    def _write_image_from_response(self, bin_image, path):
        with safe_open(path, 'wb') as f:
            f.write(bin_image)
            self.download_count += 1
            f.close()

        result = os.path.isfile(path)
        LOGGER.debug('Image written at: {}, Status: {}'.format(path, result))
        return result

    def delete(self):
        try:
            os.remove(self.path)
        except FileNotFoundError as e:
            LOGGER.error('File has never been created: {}'.format(e.filename))
        self.deleted = True
        return self.deleted


class QueueList(list):
    def __init__(self, *args, started_at=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.started_at = started_at
        self.done = False

    def empty(self):
        return self == []

    def get(self):
        if self.empty():
            self.update()
        result = self[-1]
        del self[-1]
        return result

    def update(self):

        self.clear()

        new_val = str(int(self.started_at) + 1).rjust(3, '0')
        LOGGER.debug('Queue is being updated to: {}'.format(new_val))
        self.started_at = new_val
        path = "data/links{}.txt"
        if not os.path.isfile(path):
            LOGGER.debug('Path does not exist: {}, Assuming that queue is done.'.format(path))
            self.done = True
            return None

        with safe_open(path.format(self.started_at), 'r') as f:
            codes = f.read().split('\n')
            f.close()
        [self.append(code) for code in codes if code != '']
        LOGGER.debug('Appended {} new Lightshot URLS'.format(len(codes)))


def get_downloaded_list():
    path_list = list()
    image_path = Path('data/img')
    for root, _, filenames in os.walk(image_path):
        for file_name in filenames:
            path_list.append(os.path.splitext(os.path.split(os.path.join(root, file_name))[1])[0])
    return path_list


class LightShotProxyHandler(object):

    def __init__(self):
        self.generator = self.proxy_generator()
        self.count = 0
        self.original_list = None

    def get_proxy_list(self, timeout=10000, country='all', ssl='yes', anonymity='elite'):
        URL = "https://api.proxyscrape.com/?request=getproxies&proxytype=http&timeout={}&country={}&ssl={}&anonymity={}".format(
            timeout, country, ssl, anonymity)
        r = requests.get(URL)
        content = r.content
        if type(r.content) == bytes:
            content = r.content.decode()

        result = list(filter(lambda x: x != '', content.split('\r\n')))
        LOGGER.debug(
            'Fetched {} new proxies with following conditions: country={country}, ssl={ssl}, anonymity={anonymity}'.format(
                len(result), country=country, ssl=ssl, anonymity=anonymity))
        self.count = len(result)
        self.original_list = result
        return result

    def proxy_generator(self):
        count = 0
        proxy_list = self.get_proxy_list()
        while True:
            try:
                yield proxy_list[count]
                count += 1
            except IndexError:
                proxy_list = self.get_proxy_list()
                count = 0
                continue

    def install_next_proxy(self):
        opener = self.return_opener()
        LOGGER.debug('Installing new opener to urllib')
        urllib.request.install_opener(opener)

    def return_opener(self):
        host = next(self.generator)
        LOGGER.debug('Created opener with host: {}'.format(host))
        proxy_dict = {'http': host}
        proxy_support = urllib.request.ProxyHandler(proxy_dict)
        opener = urllib.request.build_opener(proxy_support)
        return opener


if __name__ == '__main__':
    counter = 0

    proxy_handler = LightShotProxyHandler()
    proxy_gen = proxy_handler.proxy_generator()
    proxy_handler.install_next_proxy()
    if not Path('data/img').exists():
        Path('data/img').mkdir()

    with safe_open("data/links022.txt", 'r') as f:
        codes = f.read().split('\n')
        f.close()

    queue = QueueList([code for code in codes if code != ''], started_at="052")

    then = time.time()

    #for i in range(proxy_handler.count):
    #    request = urllib.request.Request('https://websniffer.cc/my',
    #                                     headers={'X-Forwarded-For': '199.232.53.140', 'X-Forwarded-Port': '420'})

    #    opener = proxy_handler.return_opener()
    #    res = opener.open(request)
    #    soup = BeautifulSoup(res.read(), 'html.parser')
    #    for tag in soup.find_all('a', href=True):
    #        if 'ip' in tag['href']:
    #            print(tag.text)
    #            print(tag.text in proxy_handler.original_list)

    #quit(0)
    image = ImageDownloader(queue, proxy_handler_instance=proxy_handler, max_requests_per_proxy=20, stop_at=10000)
    image.run()

    LOGGER.debug('Finished job. Time taken: {}'.format(time.time() - then))

    quit(0)
