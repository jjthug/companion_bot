100k token per hour

PLANS
=====
llm (gemini 2.5-flash) with gsearch, news, weather apis

100 users, 30 min/day
---------
cloud run => 10$
postgres db => 15$
redis => 35$
TOTAL => 60$

100 users => 500$


30 min/ day:
============
LLM+context+tools(gsearch,weather,news)
200k + 150k + 20k tokens = 500k tokens => 0.15 + 0.05 => 0.2$/30 min => 6$/month

cloud run => 0.1$
redis => 0.1$
postgres => 0.2$
total cost => 7$

price => 18$ => 17.99$
apple cut => 6$
net => 5$


1 hr/day
========
LLM+context+tools(gsearch,weather,news)
1.1 M tokens => 0.5$/hr => 15$/month
services=1$
price=30$
apple=9$
net=5$

