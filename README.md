> TODO
> pg_dump -h 10.12.77.188 -p 5432 -U postgres -s -f devdb.sql devdb
> psql -h 10.12.77.188 -p 5432 -U postgres xxDB < devdb.sql

sudo mount -o resvport -t nfs 10.12.78.89:/home/test/venus_be/instance /home/shopeeqa/kobe/venus_be/instance

docker run --privileged -it --network=host \
 -v `pwd`:/run \
 --name xgg \
 harbor.shopeemobile.com/autotest/apitesttool:v1.0 \
 /bin/bash

docker exec -it `docker run --privileged -it -d -v $(pwd):/home/admin go /usr/sbin/init` /bin/bash

docker run --privileged -it -d -v /home/arrow:/run -e SWAGGER_JSON=/run/openapi.yaml swaggerapi/swagger-ui bash

docker run --privileged -it -d -v `pwd`/mynginx.conf:/etc/nginx/conf.d/default.conf -p 8888:80 --name=myng nginx


# test1
# test2

# test3

# test4

# test5

