#!/usr/bin/python
from datetime import datetime, timedelta
import time
import re
from itertools import *

YmdHM = "%Y:%m:%d:%H:%M"    # standard formatting of datetime-input
extra = timedelta  # alias to make it easy

# helpermethods taht return the start, the end and the start/end  of different timeunits
def startofyear(date):
    return datetime(year=date.year,  month=1,  day=1,  hour=0,  minute=0)


def endofyear(date):
    return datetime(year=date.year+1,  month=1,  day=1,  hour=0,  minute=0)


def startofmonth(date):
    return datetime(year=date.year,  month=date.month,  day=1,  hour=0,
                    minute=0)


def endofmonth(datex):
    date = (startofmonth(datex)+extra(days=32)).replace(day=1)
    return datetime(year=date.year, month=date.month, day=1, hour=0, minute=0)


def startofday(date):
    return datetime(year=date.year, month=date.month, day=date.day, hour=0,
                    minute=0)


def endofday(datex):
    date = startofday(datex)+extra(days=1)
    return datetime(year=date.year, month=date.month, day=date.day, hour=0,
                    minute=0)


def startofhour(date):
    return datetime(year=date.year, month=date.month, day=date.day,
                    hour=date.hour, minute=0)


def endofhour(datex):
    date = startofhour(datex)+extra(hours=1)
    return datetime(year=date.year, month=date.month, day=date.day,
                    hour=date.hour, minute=0)


def startofminute(date):
    return datetime(year=date.year, month=date.month, day=date.day,
                    hour=date.hour, minute=date.minute)


def endofminute(datex):
    date = startofminute(datex)+timespan(minute=1)
    return datetime(year=date.year, month=date.month, day=date.day,
                    hour=date.hour, minute=date)


def startofweek(datex):
    weekday = datex.weekday()
    monday = datex-extra(days=weekday)
    return startofday(monday)


def endofweek(datex):
    weekday = datex.weekday()
    nextsunday = datex+extra(days=7-weekday)
    return endofday(nextsunday)


def rangeyear(date):
    return startofyear(date), endofyear(date)


def rangemonth(date):
    return startofmonth(date), endofmonth(date)


def rangeday(date):
    return startofday(date), endofday(date)


def rangehour(date):
    return startofhour(date), endofhour(date)


def rangeminute(date):
    return startofminute(date), startofminute(date)


def rangeweek(date):
    return startofweek(date), endofweek(date)


# this* returns the start of d, m, h, y, mi till  now


def thisyear(date, i):
    return startofyear(date), date


def thismonth(date, i):
    return startofmonth(date), date


def thisday(date, i):
    return startofday(date), date


def thishour(date, i):
    return startofhour(date), date


def thisminute(date, i):
    return startofminute(date), date


def thisweek(date, i):
    return startofweek(date), date


def thismorning(date, i):
    beginx = startofday(date)
    begin = beginx+extra(hours=6)
    end = begin + extra(hours=6)
    return begin, end


def thisevening(date, i):
    bx, ex = thisafternoon(date, i)
    begin = ex
    end = ex + extra(hours=6)
    return begin, end


def thisafternoon(date, i):
    bx, ex = thismorning(date, i)
    begin = ex
    end = ex + extra(hours=6)
    return begin, end


def thisnight(date, i):
    bx, ex = thisevening(date, i)
    begin = ex
    end = ex + extra(hours=6)
    return begin, end

#   prev* y, m, d, h, m,...  means :inclusive now, count back y, m, d, ...
#   if now is the end of the month count back to the end of the previous months
#   ex: if your halfway april you get the same date in feb;if you are 30 or
#   31 april you get the last day of feb"""


def prevyear(date, i):
    som = startofmonth(date)
    yearagomonth = som.replace(year=(date.year - 1*i))
    yearago = yearagomonth+extra(days=date.day-1, hours=date.hour,
                                 minutes=date.minute)
    return yearago, date


def prevmonth(datex, i):
    date = datex
    for i in range(i):
        lastday = (date + extra(days=1)).day
        thisday = date.day
        prem = startofmonth(date - extra(days=1))
        thatday = prem.day
        if lastday == 1:
            if thatday <= thisday:
                firstprem = prem.replace(day=thatday)
            else:
                firstprem = prem.replace(day=thatday)
        else:
            if thisday > thatday:
                firstprem = prem.replace(day=thatday)
            else:
                firstprem = prem.replace(day=thisday)
        date = firstprem + extra(hours=date.hour, minutes=date.minute)
    monthago = date
    return monthago, datex


def prevday(date, i):
    return date-extra(days=1*i), date


def prevhour(date, i):
    return date-extra(hours=1*i), date


def prevminute(date, i):
    return date-extra(minutes=1*i), date


def prevweek(date, i):
    startprevweek = startofday(date-extra(days=date.weekday()))-extra(7*(i-1))
    return startprevweek, date


def prevmorning(date, i):
    yesterday = startofday(date) - extra(days=(1*i))
    begin = yesterday + extra(hours=6)
    end = begin + extra(hours=6)
    return begin, end


def prevafternoon(date, i):
    __, begin = prevmorning(date, i)
    end = begin + extra(hours=6)
    return begin, end


def prevevening(date, i):
    __,  begin = prevafternoon(date, i)
    end = begin + extra(hours=6)
    return begin, end


def prevnight(date, i):
    end = startofday(date) - extra(days=(1*i))
    begin = end - extra(hours=6)
    return begin, end


#   last y, m, d, ... means: the whole previous y m d h m, not till now


def lastyear(date, i):
    end = startofyear(date)
    begin = end.replace(year=(end.year-(1*i)))
    return begin, end


def lastmonth(date, i):
    end = startofmonth(date)
    start = end
    for x in range(i):
        prevmonth = start-extra(days=1)
        start = prevmonth.replace(day=1)
    begin = start
    return begin, end


def lastday(date, i):
    end = startofday(date)
    begin = end-extra(days=(i*1))
    return begin, end


def lasthour(date, i):
    end = startofhour(date)
    begin = end - extra(hours=(i*1))
    return begin, end


def lastminute(date, i):
    end = startofminute(date)
    begin = end - extra(minutes=(i*1))
    return begin, end


def lastweek(date, i):
    end = startofday(date - extra(days=date.weekday()))
    begin = end - extra(days=(7*i))
    return begin, end


def lastnight(date, i):
    begin = startofday(date) - extra(days=(1*i))
    end = begin + extra(hours=6)
    return begin, end


def lastevening(date, i):
    end = startofday(date) - extra(days=(1*i))
    begin = end - extra(hours=6)
    return begin, end


#   helpermethods that do the work


def getwordsrange(words):
    third = 1  # if you ask for prev 6 days this is the 6
    a, b, c = words[0]
    if b.strip().isdigit():
        third = int(b)
    if a in TODAY:
        first = "THIS"
        second = "DAY"
    elif a in YESTERDAY:
        first = "PREV"
        second = "DAY"
    elif a:
        first = [cat for cat, i in timeUnits.items() if a in i][0]
    if c:
        second = [cat for cat, i in timeUnits.items() if c in i][0]
    a = SOLUTION[first][second]
    begin, end = a(datetime.now(), third) # this calls all the above methods
    return begin, end


def process((a, b, c)):
    """this should take care of the + and = and x in exact date queries
       it copies itself, resets,... starting from the datetime now
       the asked-for number gets put in the slot m, h, d, M, Y
       = copies the number of the now-slot m, h, d, M, Y
       x sets the number to zero in the slot m, h, d, M, Y
    """
    if not b:
        return str(a)
    if b == '=':
        return str(a)
    if b == 'x':
        return str(c(0))
    if int(b) < 0:
        return str(c(a+int(b)))
    if int(b) >= 0:
        return str(c(int(b)))


def fromdigits(ip):
    #  parses the input to a wellformed datetime 
    n = -1
    a = ["x"]*5
    for m in re.finditer(digitaldate,  ip):
        n = n+1
        if n < 5:
            a[n] = (m.group(1))
    return a

#  helpers to check the min/max of date
def checkyear(y):
    if y < 1900:
        return 1900 # lowest allowed in structs
    return y if y < 9999 else 99999


def checkmonths(M):
    if M <= 0:
        return 1
    return M if (M > 0 and M < 13) else 12


def checkdays(d):
    if d <= 0:
        return 1
    return d if (d > 0 and d < 31) else 31


def checkhours(h):
    return h if (h > -1 and h < 25) else 0


def checkminutes(m):
    return m if (m > -1 and m < 61) else 0

# stick all the checkers in a tuple for easy access
checkmethods = (checkyear, checkmonths, checkdays, checkhours, checkminutes)


def nowformatted():
    return datetime.now().strftime(YmdHM).split(":")


def getnumbersrange(numbers):
    timeunit = 0   # this is the datetimeslot the user wants...year, month, day
    for i, l in enumerate(numbers):
        if l.isdigit() or l == "=":
            timeunit = i

    nstr = nowformatted()  # datetime now formatted

    inputdate = ":".join(imap(process, izip_longest(nstr, numbers,
                                                    checkmethods)))
    onedate = datetime.strptime(inputdate, YmdHM)
    #  now we have to maximise it
    #  so that it makes the asked-for date inclusive
    #  so 2012/08 becomes 2012/09/01 at midnight
    if timeunit == 0:
        begin, end = rangeyear(onedate)
    if timeunit == 1:
        begin, end = rangemonth(onedate)
    if timeunit == 2:
        begin, end = rangeday(onedate)
    if timeunit == 3:
        begin, end = rangehour(onedate)
    if timeunit == 4:
        begin, end = rangeminute(onedate)
    return begin, end


#  collection of words used to parse time requests
#  maybe let user add their own words to this ???
PREV = ("prev", "p")
LAST = ("last", "l")
THIS = ("this", "t")
YEAR = ("years", "year", "y")
MONTH = ("months", "month", "m", "mo")
WEEK = ("weeks", "week", "w")
DAY = ("days", "day", "d")
HOUR = ("hours", "hour", "h")
MINUTE = ("minutes", "minute", "mi")
MORNING = ("morning", "mor")
AFTERNOON = ("afternoon", "aft")
EVENING = ("evening", "eve")
NIGHT = ("night", "nig", "tonight")
WEEKDAYS = ("monday", "thuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday")
TODAY = ("today", "now")
YESTERDAY = ("yesterday", "yes")
itswords = PREV+LAST+THIS+YEAR+MONTH+WEEK+DAY+HOUR+MINUTE+MORNING+AFTERNOON\
    + EVENING+NIGHT+WEEKDAYS+TODAY+YESTERDAY
timeUnits = {"YEAR": YEAR, "MONTH": MONTH, "WEEK": WEEK, "DAY": DAY,
             "HOUR": HOUR, "MINUTE": MINUTE, "THIS": THIS, "LAST": LAST,
             "PREV": PREV, "NIGHT": NIGHT, "MORNING": MORNING,
             "AFTERNOON": AFTERNOON, "EVENING": EVENING}


#  regexpatterns to parse input
digitaldate = re.compile('(=|x|(-[0-9]+)|([0-9]+))')
alphadate = re.compile('([a-zA-Z]+)(\s*\d*\s*)([a-zA-Z]*)') 
onedigitaldate = re.compile('(=|x|[0-9]+)')
digits = re.compile('[0-9]+')
ellipsepat = re.compile('(.*)(\.\.)(.*)')


THIS = {"YEAR": thisyear, "MONTH": thismonth, "WEEK": thisweek, "DAY": thisday,
        "HOUR": thishour, "MINUTE": thisminute, "MORNING": thismorning,
        "AFTERNOON": thisafternoon, "EVENING": thisevening, "NIGHT": thisnight}
LAST = {"YEAR": lastyear, "MONTH": lastmonth, "WEEK": lastweek, "DAY": lastday,
        "HOUR": lasthour, "MINUTE": lastminute, "NIGHT": lastnight,
        "EVENING": lastevening}
PREV = {"YEAR": prevyear, "MONTH": prevmonth, "WEEK": prevweek, "DAY": prevday,
        "HOUR": prevhour, "MINUTE": prevminute, "MORNING": prevmorning,
        "AFTERNOON": prevafternoon, "EVENING": prevevening, "NIGHT": prevnight}
SOLUTION = {"THIS": THIS, "PREV": PREV, "LAST": LAST}


def makestructfromdatetime(dt):
    """given a datetime returns a struct"""
    return dt.timetuple()


def makefloatfromstruct(t):
    """ given a struct returns a float"""
    try:
        return time.mktime(t)
    except Exception, e:
        print "caught:", e


def makefloatfromdatetime(dt):
    """given a datetime returns a float"""
    return makefloatfromstruct(makestructfromdatetime(dt))


def getinput(n):
    """puts up a command prompt to get input"""
    print ">", n
    return convertinput(re.sub('\s+\.\.\s+', '..', raw_input(">")))


def inputstring(n):
    """ use this to ask input queries it returns min, max float"""
    b, e = convertinput(re.sub('\s+\.\.s+', '..', n))
    return (makefloatfromdatetime(b), makefloatfromdatetime(e))


def convertinput(ip):
    """ see if we have an ellipse, so 2 requests"""
    m = re.findall(ellipsepat, ip)
    if m:
        return get_range_fromEllipseInput(m)
    else:
        return get_range_fromSingleInput(ip)


def get_range_fromSingleInput(ip):
    """ 1 input, see if its num or words"""
    if any(word in ip.split() for word in itswords):
        words = re.findall(alphadate, ip)
        begin, end = getwordsrange(words)

    else:
        numbers = re.finditer(digitaldate, ip)
        date = [n.group(1) for n in numbers][:6]
        begin, end = getnumbersrange(date)

    return begin, end


def get_range_fromEllipseInput(m):
    """2 requests, split them up and get the min max"""
    a, b, c = m[0]
    begin = ""
    end = ""
    if a != ".." and a != "":
        begin,  __ = get_range_fromSingleInput(a)
    if b != ".." and b != "":
        __,  end = get_range_fromSingleInput(b)
    if c != ".." and c != "":
        __,  end = get_range_fromSingleInput(c)
    if not begin:
        begin = datetime(1990, 01, 01)
    if not end:
        end = datetime.max
    return begin, end


if __name__ == '__main__':
    """ this module returns a min-float,max-float from a request.
    The request can be a verbal request or a numeric request
    a verbal request is ex: this afternoon, yesterday, last night, 
    this week, last 2 months, prev year, last year, this year,
    prev 5 months..yesterday night, this morning.. prev 2 minutes
    a numeric request is ex: 2012.10.(returns the whole 10th month)
    2012..2013.02(start of 2012 upto 2013.03.01 00:00:00)
    You can combine verbal and numeric requests ex: 2012..last night
    verbal requests: 3 parts of which the second part is a number
    the first part can be :
    this: this year, month, week, day, hour, minute, morning,
          afternoon, evening, night
    last:returns the last year, month,week... till now, so :now is
         the end and  count year, month back...
         if its friday than last week is friday to now
    prev : if its friday than the prev week is ending the sunday
        before and a week further back 
    and then there are these special words: yesterday, today
    for numeric requests: 2012/10/12/23/59(Y,m,d,H,mi)
    when you give part of this, it gets that: 2012 gives you all of 2012
    2012/10/01 gives you everything form the first of 10
    if you put in a '=' , you copy the number form now
    so 2012==== copies the values form today after the 2012. 
    an x sets the value to zero 2012:10xxxx(its okay to give 
    more x-es or =-es, gets cut off) is 2012/10/01/00:00
    You cann't do 20121001, we need something between the numbers,;:/
    are all okay
    spaces or not before after '..' is ok
    for beets users ;:if you got whitespace between words you should
     use " or ' at the beginning and end"""
