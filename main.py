"""
Usage: Start script, then use you web browser, wget, etc. to visit:
    http://localhost:8080/world/
    http://localhost:8080/world2/
"""
from gevent.monkey import patch_socket
patch_socket()
import logging
import gevent
import webapp2
from gevent import wsgi
from gevent.event import AsyncResult
from webob import exc


class EventLoopRequestContext(webapp2.RequestContext):
    """
    Override webapp2.RequestContext in order to avoid setting thread-local variables, since we're always working
    in a single thread with gevent.
    """
    def __enter__(self):
        """
        Same as in webapp2.RequestContext, except that thread-local variables are not set.
        """
        request = self.app.request_class(self.environ)
        response = self.app.response_class()
        # Make active app and response available through the request object.
        request.app = self.app
        request.response = response
        return request, response

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Skipping thread-local tear-down
        """
        pass


class ListenerRoute(webapp2.Route):
    def __init__(self, template, handler, async_result, methods=None, schemes=None):
        super(ListenerRoute, self).__init__(template, handler=handler, methods=methods, schemes=schemes)
        self.async_result = async_result

    def set_async_result(self, result):
        self.async_result.set(result)


class ListenerRouter(webapp2.Router):
    """
    A faster Router that looks up a static path definition in a dict instead of iterating through webapp routes.
    """
    def __init__(self, routes):
        pass

    def dispatch(self, request, response):
        route, route_args, route_kwargs = self.match(request)
        res = route.handler(request, response, *route_args, **route_kwargs)
        route.set_async_result(res)
        return response

    def match(self, request):
        routes = request.app.routes
        method_not_allowed = False
        for n, route in enumerate(routes):
            try:
                match = route.match(request)
                if match:
                    routes.pop(n)
                    return match
            except exc.HTTPMethodNotAllowed:
                method_not_allowed = True

        if method_not_allowed:
            raise exc.HTTPMethodNotAllowed()

        raise exc.HTTPNotFound()


class CallbackWSGIApplication(webapp2.WSGIApplication):
    routes = []
    request_context_class = EventLoopRequestContext
    router_class = ListenerRouter

    def __init__(self, debug=False, config=None):
        super(CallbackWSGIApplication, self).__init__(routes=None, debug=debug, config=config)

    @classmethod
    def spawn(cls, hostport):
        return gevent.spawn()

    def add_listener(self, path, listener, methods=None, schemes=None):
        async_result = AsyncResult()
        self.routes.append((ListenerRoute(path, listener, async_result, methods=methods, schemes=schemes)))

        def get_res():
            logging.debug("LISTENING TO: %s" % path)
            res = async_result.get()  # This will block until async_result.set() has been called some other place
            logging.debug("GOT REQUEST ON: %s" % path)
            gevent.sleep()  # Yield control to event-loop so that the CallbackWSGIApplication is
                            # able to receive the next request
            logging.debug("WAKING %s" % path)
            return res
        return gevent.spawn(get_res)


class SpawningWSGIServer(wsgi.WSGIServer):
    server_job = None

    def serve_forever(self, stop_timeout=None):
        if self.server_job is None:
            self.server_job = gevent.spawn(super(SpawningWSGIServer, self).serve_forever)

    def stop(self, timeout=None):
        super(SpawningWSGIServer, self).stop(timeout=timeout)
        if self.server_job is not None:
            self.server_job.join()


if __name__ == '__main__':
    application = CallbackWSGIApplication()
    server = SpawningWSGIServer(('', 8080), application)
    try:
        server.serve_forever()

        def listener(request, response):
            response.write('Hello ' + request.path.replace('/', ' '))
            return request

        world_job = application.add_listener('/world/', listener)
        world2_job = application.add_listener('/world2/', listener)

        gevent.joinall((world_job, world2_job))  # Blocking until GET has been called on both '/world/' and '/world2/'
        print "RES 1:", world_job.value
        print "RES 2:", world2_job.value
    finally:
        server.stop()

