# Originial Project

[scrapy-selenium](https://github.com/clemfromspace/scrapy-selenium)

# Problem

the orginal package could only open one browser driver at a time, which is quite slow for a scrapy

# Adaptation

**I rewrote middlewares.py inorder to enable multiple browser drivers at same time**

## Configuration

After following the Configuration step in orginal project, you can also set:

- SELENIUM_DRIVER_POOL_SIZE(default = 5)
- SELENIUM_QUEUE_TIMEOUT(default = 300)

## Result

**Now, you can open multiple browser drivers at one time! Enjoy your scrapy journey.**  
