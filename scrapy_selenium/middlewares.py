from importlib import import_module
from selenium.webdriver.support.ui import WebDriverWait
from selenium import webdriver
from scrapy.http import HtmlResponse
from scrapy.exceptions import NotConfigured
from scrapy import signals
from scrapy.downloadermiddlewares.useragent import UserAgentMiddleware
import random
from queue import Queue
from .http import SeleniumRequest

class SeleniumMiddleware:
    """Scrapy middleware handling the requests using Selenium"""

    def __init__(self, driver_name, driver_executable_path,
                 browser_executable_path, command_executor, driver_arguments, pool_size, queue_timeout):
        """Initialize the Selenium middleware"""
        self.driver_name = driver_name
        self.driver_executable_path = driver_executable_path
        self.browser_executable_path = browser_executable_path
        self.command_executor = command_executor
        self.driver_arguments = driver_arguments
        self.pool_size = pool_size
        self.queue_timeout = queue_timeout
        self.driver_pool = Queue(maxsize=pool_size)
        for _ in range(pool_size):
            self.driver_pool.put(self.create_driver())


    @classmethod
    def from_crawler(cls, crawler):
        """Initialize the middleware with the crawler settings"""
        driver_name = crawler.settings.get('SELENIUM_DRIVER_NAME')
        driver_executable_path = crawler.settings.get('SELENIUM_DRIVER_EXECUTABLE_PATH')
        browser_executable_path = crawler.settings.get('SELENIUM_BROWSER_EXECUTABLE_PATH')
        command_executor = crawler.settings.get('SELENIUM_COMMAND_EXECUTOR')
        driver_arguments = crawler.settings.get('SELENIUM_DRIVER_ARGUMENTS')
        pool_size = crawler.settings.get('SELENIUM_DRIVER_POOL_SIZE', 5)
        queue_timeout = crawler.settings.get('SELENIUM_QUEUE_TIMEOUT', 300)

        if driver_name is None:
            raise NotConfigured('SELENIUM_DRIVER_NAME must be set')

        middleware = cls(
            driver_name=driver_name,
            driver_executable_path=driver_executable_path,
            browser_executable_path=browser_executable_path,
            command_executor=command_executor,
            driver_arguments=driver_arguments,
            pool_size = pool_size,
            queue_timeout=queue_timeout
        )

        crawler.signals.connect(middleware.spider_closed, signals.spider_closed)

        return middleware

    def create_driver(self):
        """Create a new Selenium driver instance"""
        webdriver_base_path = f'selenium.webdriver.{self.driver_name}'

        driver_klass_module = import_module(f'{webdriver_base_path}.webdriver')
        driver_klass = getattr(driver_klass_module, 'WebDriver')

        driver_options_module = import_module(f'{webdriver_base_path}.options')
        driver_options_klass = getattr(driver_options_module, 'Options')

        driver_options = driver_options_klass()

        if self.browser_executable_path:
            driver_options.binary_location = self.browser_executable_path
        for argument in self.driver_arguments:
            driver_options.add_argument(argument)

        driver_kwargs = {
            'executable_path': self.driver_executable_path,
            f'{self.driver_name}_options': driver_options
        }

        # locally installed driver
        if self.driver_executable_path is not None:
            driver_kwargs = {
                'executable_path': self.driver_executable_path,
                f'{self.driver_name}_options': driver_options
            }
            driver = driver_klass(**driver_kwargs)
        # remote driver
        elif self.command_executor is not None:
            from selenium import webdriver
            capabilities = driver_options.to_capabilities()
            driver = webdriver.Remote(command_executor=self.command_executor,
                                           desired_capabilities=capabilities)
        # webdriver-manager
        else:
            # selenium4+ & webdriver-manager
            from selenium import webdriver
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service as ChromeService
            if self.driver_name and self.driver_name.lower() == 'chrome':
                # options = webdriver.ChromeOptions()
                # options.add_argument(o)
                driver = webdriver.Chrome(options=driver_options,
                                               service=ChromeService(ChromeDriverManager().install()))
        return driver

    def process_request(self, request, spider):
        """Process a request using the Selenium driver if applicable"""
        if not isinstance(request, SeleniumRequest):
            return None

        try:
            # Get a driver from the pool, waiting up to self.queue_timeout seconds if necessary
            driver = self.driver_pool.get(timeout=self.queue_timeout)
        except Empty:
            logging.error(f"No available Selenium drivers within {self.queue_timeout} seconds")
            return None

        try:
            driver.get(request.url)

            for cookie_name, cookie_value in request.cookies.items():
                driver.add_cookie(
                    {
                        'name': cookie_name,
                        'value': cookie_value
                    }
                )

            if request.wait_until:
                WebDriverWait(driver, request.wait_time).until(
                    request.wait_until
                )

            if request.screenshot:
                request.meta['screenshot'] = driver.get_screenshot_as_png()

            if request.script:
                driver.execute_script(request.script)

            body = str.encode(driver.page_source)

           # Expose the driver via the "meta" attribute
            request.meta.update({'driver': driver})

            return HtmlResponse(
                driver.current_url,
                body=body,
                encoding='utf-8',
                request=request
            )
        except Exception:
            driver.quit()
            self.driver_pool.put(self.create_driver())
            raise
        finally:
            self.driver_pool.put(driver)

    def spider_closed(self):
        """Shutdown the driver when the spider is closed"""
        while not self.driver_pool.empty():
            driver = self.driver_pool.get()
            if driver is not None:
                driver.quit()
        # if self.driver is not None:
        #     self.driver.quit()

class MyUserAgentMiddleware(UserAgentMiddleware):
    '''
    设置User-Agent
    '''

    def __init__(self, user_agent):
        self.user_agent = user_agent

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            user_agent=crawler.settings.get('MY_USER_AGENT')
        )

    def process_request(self, request, spider):
        agent = random.choice(self.user_agent)
        request.headers['User-Agent'] = agent

