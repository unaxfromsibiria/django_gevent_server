def warm_cache(uid):
    # create once subprocess
    if '0' not in uid:
        return

    import gevent

    while True:
        # do any think
        print 'I run every second!'
        gevent.sleep(1.0)
