# Hummingbot Source Code

This folder contains the main source code for Hummingbot.

## Project Breakdown
```
hummingbot
│
├── client					# CLI related files
│
├── connector				# connectors to individual exchanges
│   ├── derivative			# derivative connectors
│   ├── exchange	 		# spot exchanges
│   ├── gateway				# gateway connectors
│   ├── other				# misc connectors	
│   ├── test_support			# utilities and frameworks for testing connectors
│   └── utilities			# helper functions / libraries that support connector functions
│
├── core
│   ├── api_throttler			# api throttling mechanism
│   ├── cpp				# high performance data types written in .cpp
│   ├── data_type			# key data
│   ├── event				# defined events and event-tracking related files								
│   ├── gateway				# gateway related components
│   ├── management			# management related functionality such as console and diagnostic tools
│   ├── mock_api			# mock implementation of APIs for testing
│   ├── rate_oracle			# manages exchange rates from different sources 
│   ├── utils				# helper functions and bot plugins		
│   └── web_assistant			# web related functionalities
│
├── data_feed				# price feeds such as CoinCap
│
├── logger				# handles logging functionality
│
├── model				# data models for managing DB migrations and market data structures
│
├── notifier				# connectors to services that sends notifications such as Telegram
│
├── pmm_script				# Script Strategies
│
├── remote_iface			# remote interface for external services like MQTT
│
├── smart_components			# smart components like controllers, executors and frameworks for strategy implementation
│   ├── controllers			# controllers scripts for various trading strategy or algorithm				
│   ├── executors			# various executors 
│   ├── strategy_frameworks 		# base frameworks for strategies including backtesting and base classes
│   └── utils				# utility scripts and modules that support smart components
│
├── strategy				# high level strategies that works with every market	
│
├── templates				# templates for config files: general, strategy, and logging
│
└── user				# handles user-specific data like balances across exchanges
```
