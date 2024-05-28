docker tag harbor.shopeemobile.com/autotest/dd:v1 harbor.shopeemobile.com/autotest/dd:v12
docker push harbor.shopeemobile.com/autotest/dd:v12

docker tag harbor.shopeemobile.com/autotest/webserver:v6 harbor.shopeemobile.com/autotest/venus:v12
docker push harbor.shopeemobile.com/autotest/venus:v12

docker tag harbor.shopeemobile.com/spex/spgen-compiler:v1.2.2 harbor.shopeemobile.com/autotest/spgen-compiler:v1.2.2
docker push harbor.shopeemobile.com/autotest/spgen-compiler:v1.2.2
docker tag harbor.shopeemobile.com/autotest/spgen-compiler:v1.2.2 harbor.shopeemobile.com/spex/spgen-compiler:v1.2.2 

