import logging
import random
import time
import thread
import socket
import os
import json

from plop.collector import Collector

class PlopMiddleware(object):
    """Middlware for profiling WSGI requests."""

    logger = logging.getLogger(__name__)

    def __init__(self, application):
        self.application = application
        self.hostname = socket.gethostname()
        self.outpath = "/tmp/plop/"
        self.percent = 25

    def should_profile(self):
        """Returns true if the current request should be profiled."""
        if self.percent == 100:
            return True
        return random.randint(0, 100) % self.percent == 0

    def __call__(self, environ, start_response):
        if not self.should_profile():
            return self.application(environ, start_response)

        collector = Collector()
        collector.start()
        start = time.time()
        try:
            return self.application(environ, start_response)
        finally:
            stop = time.time()
            collector.stop()

            try:
                self.save_data(environ, start, stop, collector)
            except Exception, e:
                self.logger.exception(e)

    def save_data(self, environ, start, stop, collector):
        data = {}
        data['hostname'] = self.hostname
        data['environ'] = dict((k, v) for k, v in environ.iteritems() if isinstance(v, basestring))
        data['start_time'] = start
        data['stop_time'] = stop
        data['thread_ident'] = thread.get_ident()
        # Only take the 25 most frequent stack frames
        collector.filter(25)

        samples = []
        for stack, frequency in collector.stack_counts.iteritems():
            frames = []
            for elm in stack:
                frame = {}
                frame['file'] = elm[0]
                frame['line_no'] = elm[1]
                frame['function'] = elm[2]
                frames.append(frame)

            sample = {}
            sample['frames'] = frames
            sample['frequency'] = frequency
            samples.append(sample)

        data['samples'] = samples

        filename = '%s-%s' % (time.time(), thread.get_ident())

        if not os.path.exists(self.outpath):
            os.makedirs(self.outpath)

        with open(os.path.join(self.outpath, filename + '.json'), 'w') as fp:
            json.dump(data, fp, indent=2)
