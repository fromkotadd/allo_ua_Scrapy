import scrapy
from datetime import datetime

import selenium.common.exceptions
from scrapy.spiders import CrawlSpider

from selenium import webdriver

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time


class AlloUaProdparSpider(CrawlSpider):
	name = 'allo_ua_prodpar'
	allowed_domains = ['allo.ua']
	start_urls = ['https://allo.ua/']
	chrome_options = webdriver.ChromeOptions()
	chrome_options.add_argument(
		"user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36")
	chrome_options.headless = True

	def __init__(self):
		self.browser = webdriver.Chrome(options=self.chrome_options)
		self.wait = WebDriverWait(self.browser, 5)


	def start_requests(self, **kwargs):
		"""
		Сбор ссылок на категории товаров
		"""
		self.browser.get(self.start_urls)
		self.browser.find_element_by_css_selector('button[class = mh-burger__btn]').click()

		elem = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'mh-button.mh-catalog-btn')))
		elem.click()

		catalog_linklist = self.browser.find_element_by_class_name('menu__list.js-menu__list').find_elements_by_css_selector('li[data-link]>a[class = item__link]')
		clear_catalog_linklist = [link.get_attribute('href') for link in catalog_linklist[:-1] if not any(keyword in link.get_attribute('href') for keyword in ('apple-store', 'xiaomi-store'))]

		for urllink in clear_catalog_linklist:
			yield scrapy.Request(callback=self.foo, url=urllink)


	def foo(self, response, **kwargs):
		"""
		Сбор ссылок на подкатегории товаров
		"""
		link_catalog = []
		for href in response.css('div[class="accordion__content"]>ul[class="portal-category__list"]'):
			link_catalog.append(href.css('a::attr(href)').get().split())
		for link in link_catalog[1:]:
			links = response.urljoin(''.join(link))
			yield response.follow(links, callback=self.parse_pages)


	def parse_pages(self, response, **kwargs):
		"""
		Сбор страниц каталога выбранной категории для обработки
		"""
			for href in response.css('.product-card__title::attr("href")').extract():
				url = response.urljoin(href)
				yield scrapy.Request(url, callback=self.parse)
				next_page = response.css('div.pagination__next>a::attr(href)').extract_first()
				if next_page is not None:
					yield response.follow(next_page, callback=self.parse_pages)

	def parse(self, response, **kwargs):
		"""
		Сбор данных с страницы товара
		"""

		self.browser.get(response.request.url)
		page = self.browser.find_element_by_tag_name("html")
		for keys in range(2):
			page.send_keys(Keys.PAGE_DOWN)
			time.sleep(0.1)


		try:
			self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.product-discount-list")))
			time.sleep(1)
			discount_list = self.browser.find_element_by_css_selector('ul.product-discount-list').find_elements_by_class_name('product-discount-list__item-text-title')
			special_offers = []

			for discount in discount_list:
				special_offers.append(discount.text)
			cashback = self.browser.find_element_by_class_name('p-trade__price-box').find_element_by_css_selector(
				'span.b-label__label').text
			cashback_clear = ''.join([elem for elem in cashback if elem.isalpha()])
			special_offers.append(cashback_clear)
		except selenium.common.exceptions.TimeoutException:
			special_offers = []

		if response.css('span[class = p-trade__stock-label-icon]'):
			availability = 'True'
		else:
			availability = 'False'
		if response.css('div[class = p-trade-price__old]>span[class = sum]::text').get():
			price_regular = response.css('div[class = p-trade-price__old]>span[class = sum]::text').get().encode(
				'ascii', 'ignore')
		else:
			price_regular = None
		if response.css("meta[itemprop = price]::attr(content)"):
			price = response.css("meta[itemprop = price]::attr(content)").get().strip()
		else:
			price = None
		if response.css('span[class = shipping-brand__name]::text').get():
			seller = response.css('span[class = shipping-brand__name]::text').get()
		else:
			seller = 'allo'

		item = {
			'scanned_at': datetime.now().isoformat(),
			'title': response.css('h1.p-view__header-title::text').get().strip(),
			'url': response.request.url,
			'sku': response.css('span.p-tabs__sku-value::text').get().strip(),
			'category': response.css('ul[id = breadcrumbs]>li>a::text').getall(),
			'availability': availability,
			'price': price,
			'price_regular': price_regular,
			'seller': seller,
			'special_offers': special_offers
		}
		yield item