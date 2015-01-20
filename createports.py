import redis

ports = [2222, 2223, 2224,2225,2226, 2227, 2228, 2229, 2230]

if __name__ == '__main__':
    r = redis.Redis()
    print "First cleaning the existing ports."
    r.delete("tunirports")
    for p in ports:
        r.lpush('tunirports', p)
