#!/bin/bash
echo "--- start ---"

echo "--- pull ---"
# docker pull harbor.shopeemobile.com/autotest/venus:v13
# docker pull harbor.shopeemobile.com/autotest/dd:v13
# docker-compose -p venus -f docker-compose_server_live.yml pull


# echo "--- build ---"
docker-compose -p venus -f docker-compose_server_live.yml build

echo "--- down ---"
docker-compose -p venus -f docker-compose_server_live.yml down



# rm -rf migrations
echo "--- restart webserver ---"
# docker-compose -p venus -f docker-compose_server_live.yml restart webserver
# docker-compose -p venus -f docker-compose_server_live.yml stop webserver
# docker-compose -p venus -f docker-compose_server_live.yml rm -f webserver


docker-compose -p venus -f docker-compose_server_live.yml up -d

echo "--- re create ---"
docker-compose -p venus -f docker-compose_server_live.yml exec -T webserver flask db_helper create
docker-compose -p venus -f docker-compose_server_live.yml exec -T webserver flask db init
echo "--- migrate ---"
docker-compose -p venus -f docker-compose_server_live.yml exec -T webserver flask db migrate
echo "--- upgrade ---"
docker-compose -p venus -f docker-compose_server_live.yml exec -T webserver flask db upgrade


echo "--- end ---"