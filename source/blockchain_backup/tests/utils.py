#!/usr/bin/env python3
'''
    Test utilities for Blockchain Backup.

    Copyright 2019-2020 DeNova
    Last modified: 2020-10-24
'''
import os, time

from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.common.exceptions import NoAlertPresentException, NoSuchElementException, StaleElementReferenceException, UnexpectedAlertPresentException
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.firefox.webdriver import WebDriver
from selenium.webdriver.support.expected_conditions import element_to_be_clickable
from selenium.webdriver.support.wait import WebDriverWait

from denova.python.log import Log
from denova.python.times import timestamp

from blockchain_backup.settings import CONTENT_HOME_URL

log = Log()

class BlockchainBackupTestCase(StaticLiveServerTestCase):
    ''' Superclass for blockchain_backup test cases. '''

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.driver = WebDriver()
        cls.wait = WebDriverWait(cls.driver, 20)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        super().tearDownClass()

    def baseurl(self):
        return CONTENT_HOME_URL

    def pause(self, seconds=3):
        ''' Pause input for specified seconds. Default is 3. '''

        log.debug('pause {} seconds (does not stop javascript execution)'.format(seconds))
        time.sleep(seconds)

    def screenshot(self, label=None):
        ''' Save a screenshot. '''

        DIR = '/tmp/blockchain-backup.screenshots'

        if not os.path.isdir(DIR):
            os.makedirs(DIR)
        if label:
            filename = '{}.{}.png'.format(label, timestamp())
        else:
            filename = '{}.png'.format(timestamp())
        path = os.path.join(DIR, filename)
        self.driver.get_screenshot_as_file(path)
        log.debug('saved screenshot to {}'.format(path))

    def get_console_log(self):
        ''' UNTESTED. Chrome only?

            Get contents of console log.

            See  Capturing browser logs with Selenium WebDriver using Java
                 https://stackoverflow.com/questions/25431380/capuring-browser-logs-with-selenium-webdriver-using-java

                 Support for Selenium’s logging interface #284
                 https://github.com/mozilla/geckodriver/issues/284

            This may only get the data since the last call to get_console_log().
        '''

        data = self.driver.Log('browser')
        return data

    def body_text(self):
        ''' Return body text. '''

        body = self.driver.find_element_by_tag_name('body')
        return body.text

    def is_hidden(self, element):
        return "hidden" in element.get_attribute("class")

    def find_element(self, find_element_by, term):
        ''' Find element without (with less?) StaleElementException. '''

        """
            Modified from C code at:
                How to avoid “StaleElementReferenceException in Selenium?
                https://stackoverflow.com/questions/12967541/how-to-avoid-staleelementreferenceexception-in-selenium
        """

        MAX_FAILURES = 2

        element = None

        failures = 0
        while failures < MAX_FAILURES:
            try:
                element = find_element_by(term)
            except StaleElementException as sere:
                failures = failures + 1
                if failures >= MAX_FAILURES:
                    raise

        return element

    def find_error_element(self, id, label):
        ''' Check for an html element that contains error messages. '''

        try:
            errors = self.driver.find_element_by_id(id)

        except NoSuchElementException:
            pass

        except StaleElementReferenceException:
            pass

        except Exception as exc:
            log.debug('in find_error_element() got exception: {}'.format(type(exc))) # DEBUG
            log.debug(exc)
            raise

        else:
            # if errors element is visible, fail
            if not self.is_hidden(errors):
                why = '{} error: {}'.format(label, errors.text)
                log.debug(why)
                self.fail(why)

    def sign_in(self):
        ''' Sign in.

            If we're not on the sign-in page, we're probably signed in.
            Just log it.
        '''

        if 'Sign in' in self.driver.title:
            username_input = self.driver.find_element_by_name('username')
            username_input.send_keys('testuser')

            password_input = self.driver.find_element_by_name('password')
            password_input.send_keys('testpassword')

            sign_in_button = self.driver.find_element_by_id('sign-in-id')
            sign_in_button.click()

            #self.wait.until(lambda x: x.find_element_by_id("accounts-id").is_displayed())
            #self.assertIn('Trade with Exchanges', self.driver.title)

        else:
            log.debug('not sign-in page: {}'.format(self.driver.title))

    def sign_out(self):
        ''' Sign out. '''

        self.wait.until(lambda x: x.find_element_by_id("navbar-user-id").is_displayed())
        self.driver.find_element_by_id('navbar-user-id').click()
        self.wait.until(lambda x: x.find_element_by_id("sign-out-id").is_displayed())
        self.driver.find_element_by_id('sign-out-id').click()
        self.assertIn('You signed out successfully', self.body_text())

    def check_errors(self):
        self.find_error_element('django_errors', 'django')
        self.find_error_element('errorsdialog', 'javascript')

    def find_element_by_tag_attribute(self, tag, attribute, value):
        ''' Return element by tag and attribute value. '''

        return self.driver.find_element_by_xpath('//{}[@{}="{}"]'.format(tag, attribute, value))

    def locate_by_tag_attribute(self, tag, attribute, value):
        ''' Return locator by tag and attribute value. '''

        return (By.XPATH, '//{}[@{}="{}"]'.format(tag, attribute, value))

    def click_by_id(self, element_id):
        ''' Click on an element by id. '''

        log.debug('click_by_id() enter')
        try:
            e = self.driver.find_element_by_id(element_id)
            log.debug('click_by_id() start wait.until element_to_be_clickable #{}'.format(element_id))
            self.wait.until(element_to_be_clickable((By.ID, element_id)))
            log.debug('click_by_id() end wait.until element_to_be_clickable #{}'.format(element_id))
            element_id.click()
        except Exception as exc:
            log.debug('click_by_id() exception {}'.format(str(exc)))
            log.debug(exc)

            try:
                self.driver.execute_script('$("#{}").click();'.format(element_id))
            except Exception as exc:
                log.debug('click_by_id() after execute_script exception {}'.format(exc))
                raise

        log.debug('click_by_id() exit')
