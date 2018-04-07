#coding:utf-8
"""ModuleName:contro_panel.py
Auther: guoyudianyou@163.com
Create at 2017年8月28日21:04:36:
Description:win7_master.py 的控制面板
主要为了不输错数，让输入输出稍微友好一点。
注意:本程序天然不会重复运行，是监听接收端口造成的.
测试中  测试中
"""
# TODO 本程序需要重构 模块过多
# TODO 更多监控显示 显示五档价格情况
import time
import calendar 
import os
import sys
import signal
import threading
import collections
from io import StringIO
import pandas as pd
from datetime import datetime
from common_modules import comm_utility
from common_modules import notifier
from common_modules import tdx_net
from common_modules import fee
from common_modules import market_status
import utility
import trade_recorder
import update_surveillance_large
heartbeat_recieved = False

global __file
__file = __file__
pid_int = os.getpid()
name = input('输入本机的昵称')
ip = input('输入对方IP')
if not name.strip():
    name = 'remote'+ '*' + str(pid_int)
else:
    name = name + '*' + str(pid_int)
print('name:', name)
if not ip.strip():
    ip = 'guoyudianyou.6655.la'
print('ip:', ip)
###########
#可以自定义的一堆变量
###########
standard_position_money = 10000 # 标准头寸规模
available_money = 0 #可用余额 来自客户端
df_position = 0 # 当前真实持仓 来自客户端

preset_order_dict = {} # 预置指令表
preset_order_count = 0 # 预置指令计数器 用来产生字典键值
preset_sent_len = 0
###########
#可供更新的变量
# _internal_parameter_update() 专用
###########
var_dict = {1:('standard_position_money','标准持仓份额对应资金量'),\
            2:('available_money','当前可用资金')}
###########
#定义主菜单
###########

def _sent_h():
    #注意 有转义字符
    global available_money
    manu = \
    '''
   \33[1;33m 超牛的交易控制台\33[1;33m
    ---------- 查询 ----------
    11.委托    \t12.持仓
    13.资金
    ---------- 交易 ----------
    21.买入    \t22.卖出
   \33[1;36m aa.发送预置指令
    qq.日内市价交易*仅已有仓位*保证当日可平仓\33[1;37m
    r1.预置买入\tr2.预置卖出\33[1;33m
    ---------- 撤单 ----------
    31.撤买    \t32.撤卖
    -------- 交易开关 --------
    55.暂停    \t56.恢复
    ---------- 系统 ----------
    00.刷新    \tlog.指令记录    \33[0m
    
    1.市场状态 \t

    s.显示监控文件
    reload.监控文件重载
    -----
    st.检查心跳情况
    pid.更新realtime_eye_tdx.py的pid
    up.内部变量更新
    mail.预置命令邮件送出
    cal.交易日历
    ----------子模块----------
   \33[1;35m rec.交易记录登记 trade_recorder.py
    voc.记账凭证主系统 trade_recorder._voucher_picker()
    la.更新监控文件大单标准 update_surveillance_large.py\33[0m
    -----
    off.脱机 \ton.在线\t当前脱机状态:\33[4;33m%s\33[0m
    -----
    h.帮助 \tx.退出控制端
    v.版本 \tstop.退出控制端 和 受控端
    =========================
    当前可用资金:\33[4;%sm￥%.2f\33[0m
    ~~~~~~~~~~
    ''' 
    if available_money >= standard_position_money:
        available_money_color = '32'
    else:
        available_money_color = '31'
    manu_vars = (heartbeating.offline,available_money_color,available_money)
    print(manu % manu_vars)
###########
#外部数据读取
###########
def _surveillance_config():
    """监控文件读取"""
    file_path = '/root/input/surveillance.xls'
    df = pd.read_excel(file_path, converters={'code':str})
    return df
surveilance_df = _surveillance_config() # 当前监控文件
###########
#定义功能函数
###########
def _cal():
    '''打印全年日历表
    打印接下来10日的交易情况'''
    fmt = '%Y-%m-%d'
    year_now = time.strftime("%Y", time.localtime(time.time()))
    calendar.prcal(int(year_now))
    print(time.ctime())
    for x in range(10):
        time_now_struct = time.localtime(time.time()+x*86400)
        date_str = time.strftime(fmt,time_now_struct)
        week_str = time.strftime('%a',time_now_struct)
        week_num = time.strftime('%W',time_now_struct)
        if market_status.date_justify(date_str) == 0:
            result = '休市\33[0m'
        else:
            result = '\33[1;33m交易\33[0m'
        print("%d %s %s 第%s周 %s" %(x, date_str,result,week_num,week_str,))
    #return []
    pass


def _preset_order_mail():
    '''预置指令 邮件送出
    要求命令数量大于1'''
    print(_preset_order_mail.__doc__)
    global preset_order_dict
    global preset_sent_len
    if len(preset_order_dict) >= 1 and len(preset_order_dict) != preset_sent_len:
        preset_sent_len = len(preset_order_dict)
        df = pd.DataFrame.from_dict(preset_order_dict,orient='index')
        content = df.to_string()
        notifier.send_simple('预置指令存档'+time.ctime(), content)
        print('已发送')
    else:
        print('无预置命令 不发送')
def _internal_parameter_update(var_index=0):
    '''内部变量更新 单体'''
    global var_dict
    global standard_position_money
    global available_money 
    # 储存变量提示名
    # 检验变量存在性
    try:
        var_index = int(var_index)
    except Exception as e:
        print('不要输入字母等杂物:',e)
        return False
    if var_index not in var_dict.keys():
        print('不支持的变量序号')
        return False
    var_str = var_dict[var_index][0]
    # 载入旧值
    if var_index == 1:
        viriable = standard_position_money
    elif var_index == 2:
        viriable = available_money
    else:
        return False
    print(var_str,'现值:',viriable)
    num = input('输入'+var_str+':')
    if num.strip():
        # 新值不为空 且 是数字
        try:
            input_num = int(num)
        except Exception as e:
            print('类型出错:',e)
            return False
        print(var_str,'新值:',input_num)
        # 输入新值
        if var_index == 1:
            standard_position_money = input_num
        elif var_index == 2:
            available_money = input_num
        else:
            return False
        return True
    else:
        return False

def _sent_up():
    """内部变量更新工具
    ~~~~~~~~~~"""
    print(_sent_up.__doc__)
    global var_dict
    for x in var_dict.keys():
        print(x,var_dict[x][1],var_dict[x][0])
    print('~~~~~~~~~~')
    target = input('输入要更新的变量:')
    if _internal_parameter_update(target):
        pass
    else:
        print('放弃更新')
def _sent_s():
    '''显示监控文件 不输入代码 显示全部监控文件'''
    print(_sent_s.__doc__)
    for _code in surveilance_df['code'].values:
        print(_code,tdx_net.get_name(_code))
    print('*'*10)
    code = input('输入代码')
    if code.strip():
        print(code,tdx_net.get_name(code))
        if code in list(surveilance_df['code'].values):
            print(surveilance_df[surveilance_df.code==code])
        else:
            print('没有此项监控内容')
    else:
        print(surveilance_df)
def _sent_1():
    '''当前持仓状态'''
    global df_position
    print(_sent_1.__doc__)
    dff = surveilance_df.copy()
    dff['name'] = dff['code'].apply(tdx_net.get_name)
    code_list = dff['code']
    df_Q = tdx_net.get_security_quotes(code_list) # 获取报价
    print(time.ctime())
    dff['price'] = df_Q['price']
    dff['profit'] = (dff['price'] - dff['cost'])* dff['amount']
    dff['profit%'] = (dff['price'] -dff['cost'])/dff['cost'] * 100
    output_columns = ['code','name','price','cost','amount','profit','profit%'] # 输出表头
    pd.set_option('precision',2)
    print('\33[1;31m','*'*20,'\33[0m')
    print('\33[1;35m','真实持仓','\33[0m')
    print(dff[output_columns][(dff['price']!=0)&(dff['sim']=='N')&(dff['cost']>0)])
    print('\33[1;33m','模拟仓','\33[0m')
    print(dff[output_columns][(dff['price']!=0)&(dff['sim']=='Y')&(dff['cost']>0)])
    print('\33[1;34m','尚未开市/停牌','\33[0m')
    print(dff[output_columns][dff['price']==0])
    dff['vol_max_now'] = dff[dff['cost']<0]['code'].apply(tdx_net.get_large_vol_now)
    print('\33[1;32m','计划买入','\33[0m')
    print(dff[['code','name','price','large_volume','vol_max_now']][(dff['price']!=0)&(dff['cost']<0)])
    print('\33[1;31m','*'*20,'\33[0m')
def _sent_trade(trade_type,signal_type=True):
    '''交易程序\n需要输入代码-单价-数量
    输入x 退出'''
    print(_sent_trade.__doc__)
    if signal_type:
        print('**指令直接发送**')
    else:
        print('**添加预制指令**')
    print('~' * 10 )
    if trade_type == 'BUY':
        _promote = '[BUY]'
        _order_start = 'BUY-'
    else:
        _promote = '[SELL]'
        _order_start = 'SELL-'
    _input_keys = ['code', 'price', 'amount']
    _output_status = [False]*3
    input_content = collections.OrderedDict()
    #打印卖单的帮助
    if trade_type == 'SELL':
        if isinstance(df_position,type(int())):
            print("未查询持仓")
        else:
            print(df_position[['code','name','available']])
    else:
        print('可用余额:%.2f' % available_money)
    print('~' * 10 )
    # 循环输入数据
    for x in _input_keys:
        __content = input(_promote+'<'+x+':')
        if __content.strip():
            if __content.startswith('x') or __content.endswith('x'):
                break
            else:
                if x == 'code':
                    if isinstance(df_position,type(int())):
                        if trade_type == 'SELL' and signal_type==True:
                            print('一个持仓都没有,卖个鬼!')
                            break
                        else:
                            pass
                    else:
                        try:
                            list(df_position['code'].values)
                        except Exception as e:
                            print('出错:',e)
                            break
                        if int(__content) not in list(df_position['code'].values) and trade_type =='SELL':
                            print('没有这个持仓 不能卖')
                            break
                    if __content not in list(tdx_net.whole_code_df['code'].values):
                        print('不能识别这个代码 什么鬼')
                        break
                    _pre_close = tdx_net.get_preclose(__content)
                    print(_promote+'>证券名称:', tdx_net.get_name(__content))
                    if __content.startswith('5') or __content.startswith('1'):
                        limit_low = _pre_close*0.9 + 0.001
                        limit_up = _pre_close*1.1 - 0.001
                        print('%s\t[%.3f,%.3f,%.3f]' %(_promote+'>许可价格',limit_low,_pre_close,limit_up))
                    else:
                        limit_low = _pre_close*0.9 + 0.01
                        limit_up = _pre_close*1.1 - 0.01
                        print('%s\t[%.2f,%.2f,%.2f]' %(_promote+'>许可价格',limit_low,_pre_close,limit_up))
                elif x == 'price':
                    if float(__content) < limit_low or float(__content) > limit_up:
                        print('价格超限')
                        break
                    if trade_type == 'BUY':
                        amount = int(standard_position_money/float(__content)/100)*100
                        print('%s\t[%d,%d]\t￥%.2f' %(_promote+'>数量推荐', amount,amount+100,standard_position_money))
                        print('%s\t[%.2f,%.2f]' % (_promote+'>对应市值', amount*float(__content), (amount+100)*float(__content)))
                    else:
                        if signal_type:
                            _cost = float(df_position[df_position.code==int(input_content['code'])]['cost'].values[0])
                            _available = float(df_position[df_position.code==int(input_content['code'])]['available'].values[0])
                            _profit = _available*(float(__content)-_cost) - fee.fee(_available*float(__content),'SELL')['sum']
                            print('成本:%.3f 清仓利润:%.2f\n可用数量:%d' % (_cost,_profit,_available))
                        else:
                            pass
                elif x == 'amount':
                    if trade_type == 'SELL':
                        if signal_type:
                            _available = float(df_position[df_position.code==int(input_content['code'])]['available'].values[0])
                            if float(__content) > _available:
                                print('没有这么多持仓，退出')
                                break
                        else:
                            pass
        else:
            break
        input_content[x] = __content
    # 检查已输入的数据数量
    _output_status_num = 0
    for x in input_content.keys():
        if input_content[x] != '':
            _output_status[_output_status_num] = True
        else:
            break
        _output_status_num += 1
    # 最终数据的处理 发不发 怎么发
    if False in _output_status:
        print('放弃下单')
        pass
    else:
        output_ = _order_start+input_content['code']+','+input_content['price']+','+input_content['amount']
        print('交易指令:',output_)
        if signal_type:
            cli.sendMsg(output_)
        else:
            _preset_order_append(output_)
            print('预制已添加:',output_)

def _sent_cancel(trade_type):
    '''撤单交易 提供代码'''
    print(_sent_cancel.__doc__)
    print('~' * 10 )
    print('撤单方向:',trade_type)
    if trade_type == 'BUY':
        _direction = 'buy'
        _promote = '[CANCEL-BUY]'
    else:
        _direction = 'sell'
        _promote = '[CANCEL-SELL]'
    _input_keys = ['code']
    _output_status = [False]*1
    input_content = collections.OrderedDict()
    for x in _input_keys:
        __content = input(_promote+x+':')
        if __content.strip():
            if __content.startswith('x') or __content.endswith('x'):
                break
            else:
                input_content[x] = __content
        else:
            break
    _output_status_num = 0
    for x in input_content.keys():
        if input_content[x] != '':
            _output_status[_output_status_num] = True
        else:
            break
        _output_status_num += 1
    if False in _output_status:
        print('放弃下单')
        pass
    else:
        output_ = 'CANCEL-'+input_content['code']+','+_direction
        print(output_)
        cli.sendMsg(output_)
def preset_order_sender(_order_dict=preset_order_dict,show=True):
    '''预置指令 发送'''
    if len(_order_dict) == 0:
        print('当前指令集无内容.') 
        return None # 强制退出发送 
    # 打印部分
    # 如果是实时产生的列表，使用外部打印的内容 本地不再打印
    if show:
        print(preset_order_sender.__doc__)
        print('行号','\t','指令内容')
        for k in _order_dict.keys():
            print(k,'\t',_order_dict[k]) # 打印漂亮点
        print('~'*10)
    key = input('输入行号(x退出):')
    # 发送部分
    if key.endswith('x') or key=='':
        print('放弃发送')
    else:
        try:
            key = int(key)
            order_sent = _order_dict[key]
            print('发送预置指令:',order_sent)
            cli.sendMsg(order_sent)
        except Exception as e:
            print('发送出错:',e)
def _sent_aa():
    preset_order_sender(preset_order_dict)
def _sent_qq():
    cli.sendMsg('Q_cash') # 需要临时检查现有资金
    for x in range(2):
        print(x+1,'s')
        time.sleep(1)
    preset_order_dict_market = _generate_market_order()
    preset_order_sender(preset_order_dict_market,show=False)
def func_set_wrapper_send():
    '''发信处理 功能组
    各程序引导入口'''
    def func_set(order):
        '''互动程序'''
        global cli
        global surveilance_df
        i = os.system('clear') # 打印菜单前先清除屏幕
        order = order.lower() # 强制使用小写字母
        if order == 'h':
            _sent_h()
        elif order == '11':
            cli.sendMsg('Q_entrust')
        elif order == '12':
            cli.sendMsg('Q_position')
        elif order == '13':
            _sent_query_cash()
        elif order == '21':
            _sent_trade('BUY',True)
        elif order == '22':
            _sent_trade('SELL',True)
        elif order == 'aa':
            _sent_aa()
        elif order == 'r1':
            _sent_trade('BUY',False)
        elif order == 'r2':
            _sent_trade('SELL',False)
        elif order == 'qq':
            _sent_qq()
        elif order == '31':
            cli.sendMsg('Q_entrust')
            _sent_cancel('BUY')
        elif order == '32':
            cli.sendMsg('Q_entrust')
            _sent_cancel('SELL')
        elif order == '55':
            cli.sendMsg('HALT')
        elif order == '56':
            cli.sendMsg('RECOVERY')
        elif order == '00':
            cli.sendMsg('REFRESH')
        elif order == 's':
            _sent_s()
        elif order == 'reload':
            surveilance_df = _surveillance_config() # 当前监控文件
            print('监控文件已重载')
        elif order == '1':
            _sent_1()
        elif order == 'up':
            _sent_up()
        elif order == 'st':
            _sent_st()
        elif order == 'pid':
            _refresh_pid()
        elif order == 'mail':
            _preset_order_mail()
        elif order == 'cal':
            _cal()
        elif order == 'rec':
            trade_recorder.main()
            i = os.system('clear') # 打印菜单前先清除屏幕
            _sent_h()
        elif order == 'voc':
            trade_recorder._voucher_picker()
            i = os.system('clear') # 打印菜单前先清除屏幕
            _sent_h()
        elif order == 'la':
            update_surveillance_large.main()
            surveilance_df = _surveillance_config() # 当前监控文件
            print('监控文件已重载')
        elif order == 'v':
            print(__doc__)
            print('~' * 10 )
            print(os.popen('svn info '+__file).read())
            print('~' * 10 )
        elif order == 'log':
            cli.sendMsg('SHOW_LOG')
        elif order == 'off':
            _offline_mode(True)
        elif order == 'on':
            _offline_mode(False)
        elif order == 'x':
            _preset_order_mail()
            print('退出')
            os.kill(pid_int, signal.SIGKILL)
        elif order == 'stop':
            _sent_stop()
        else:
            _sent_h()
            print('无效指令:', order)
    return func_set
cli = comm_utility.Client(ip, name, func_set_wrapper_send())
###########
#多线程对象们
###########
class heartbeat(threading.Thread):
    '''心跳维持线程对象 信号发送
    每90s向目标发送一次REFRESH'''
    last_time = 'INIT'
    last_connect = 'INIT'
    sent_num = 0
    sent_num_sum = 0
    offline = False
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):
        while True:
            global cli
            global heartbeat_recieved
            cli.sendMsg('HEARTBEAT')
            self.last_time = time.ctime()
            #print('心跳已发送', time.ctime())
            time.sleep(15)
            if heartbeat_recieved is True:
                #print('连通', time.ctime())
                heartbeat_recieved = False
                self.last_connect = time.ctime()
                if self.sent_num >0:
                    print('heartbeat:发送次数重置 sent_num reset.')
                    print(time.ctime())
                    self.sent_num_sum += self.sent_num
                    self.sent_num = 0
            else:
                if self.offline:
                    pass
                else:
                    if self.sent_num >=5:
                        print('*'*10)
                        print('确认失联\t', time.ctime())
                        print('心跳信号\t', self.last_time)
                        print('上次连通\t', self.last_connect)
                        notifier.send_simple('受控机彻底失联 控制台退出'+time.ctime(), '最后一次成功心跳:'+self.last_time)
                        os.kill(pid_int, signal.SIGKILL)
                    else:
                        print('当前时间\t', time.ctime())
                        print('心跳信号\t', self.last_time)
                        print('上次连通\t', self.last_connect)
                        print('通知次数\t', self.sent_num)
                        if self.sent_num >=1:
                            notifier.send_simple('网络波动第'+str(self.sent_num)+'次 受控机失联 控制台待命'+time.ctime(), '最后一次成功心跳:'+self.last_time)
                        self.sent_num += 1
            time.sleep(45)
            #time.sleep(10)
class realtime_eye_watcher(threading.Thread):
    '''realtime_eye的监视程序
    这个程序总出错,也没有更好的通知方法，需要特别监控
    '''
    def __init__(self):
        threading.Thread.__init__(self)
        self.realtime_eye_pid = '0'
    def get_pid(self):
        '''获取crontab的pid'''
        _start_time= '09:26'
        _end_time= '15:00'
        _start_time_int = time.mktime(time.strptime(_start_time, '%H:%M'))
        _end_time_int = time.mktime(time.strptime(_end_time, '%H:%M'))
        _now_time = time.ctime()[-13:-8]
        _now_time_int = time.mktime(time.strptime(_now_time, '%H:%M'))
        if _start_time_int < _now_time_int < _end_time_int:
            result_str = os.popen('ps -C python|grep ?').read()
            result_list = result_str.split(' ')
            if result_list[0] == '':
                return '0'
            else:
                print('新监控:',result_list[0])
                return result_list[0]
        else:
            return '0'
    def run(self):
        while True:
            #self.realtime_eye_pid = '0'
            if int(self.realtime_eye_pid) > 0:
                _check_command_str = 'ps -aux|grep ' + self.realtime_eye_pid
                result_str = os.popen(_check_command_str).read()
                result_list = result_str.split('\n')
                if len(result_list) == 4:
                    #print('clear')
                    #print(result_list)
                    pass
                else:
                    print('盯市程序%s出错\n%s' %(self.realtime_eye_pid,time.ctime()))
                    notifier.send_simple(str(self.realtime_eye_pid)+'盯市出错'+time.ctime(), '')
                    self.realtime_eye_pid = '0'
                time.sleep(5)
            else:
                self.realtime_eye_pid = self.get_pid()
                #print('rest......')
                time.sleep(5)

check_realtime_eye = realtime_eye_watcher()
def _refresh_pid():
    '''强制刷新realtime_eye.py的pid,输入空串退出'''
    print(_refresh_pid.__doc__)
    global check_realtime_eye
    print('当前时间\t', time.ctime())
    print('当前检测PID\t', check_realtime_eye.realtime_eye_pid)
    pid_unchecked = input('输入PID：')
    if pid_unchecked == '':
        pass
    else:
        try:
            int(pid_unchecked)
            check_realtime_eye.realtime_eye_pid = pid_unchecked
        except:
            pass
    print('当前时间\t', time.ctime())
    print('当前检测PID\t', check_realtime_eye.realtime_eye_pid)

def _sent_query_cash():
    '''Q_cash系列命令
    1.可用余额
    2.冻结余额
    3.资金余额
    4.可取余额
    5.股票市值
    6.总资产
    "".可用余额
    其他.所有字段'''
    print(_sent_query_cash.__doc__)
    print('~' * 10 )
    post_fix_int = input('查询项目：')
    cli.sendMsg('Q_cash'+str(post_fix_int))
def _offline_mode(status):
    """脱机模式更改"""
    global heartbeating 
    heartbeating.offline = status
    print('heartbeating 脱机:',status,':',time.ctime())
def _sent_st():
    '''心跳检查'''
    global heartbeating
    print('当前时间\t', time.ctime())
    print('心跳信号\t', heartbeating.last_time)
    print('上次连通\t', heartbeating.last_connect)
    print('断开次数\t', heartbeating.sent_num)
    print('总断开次数\t', heartbeating.sent_num_sum)
    print('-'*5)
    print('heartbeat_recieved:',heartbeat_recieved)
def _sent_stop():
    '''退出控制端和受控端'''
    global heartbeating 
    print(_sent_stop.__doc__)
    cli.sendMsg('STOP')
    _preset_order_mail()
    for i in range(5):
        time.sleep(1)
        print(5-i)
    print('退出')
    if heartbeating.offline:
        print('脱机模式 control_panel.py 不退出.')
        pass
    else:
        os.kill(pid_int, signal.SIGKILL)
def _recieve_dataframe(order):
    '''收到dataframe的处理程序
    1.打印请求类型
    2.把收到的东西还原成df
    3.如果是内部变量，更新相应变量'''
    global df_position
    order_list = order.split('>')
    print(order_list[0])
    if order_list[-1][1:].startswith('Empty') or order_list[-1][1:].startswith('0'):
        print('空集或异常 重新查询')
    else:
        data_raw = StringIO(order_list[-1][1:])
        #df = pd.read_csv(data_raw,delim_whitespace=True,dtype={'证券代码':str}) # TODO 可能发出来的时候就没有00开头了?
        df = pd.read_csv(data_raw,delim_whitespace=True)
        if order_list[0].endswith('position'):
            df.rename(columns={'证券代码':'code',\
                           '证券名称':'name',\
                           '股票余额':'amount',\
                           '可用余额':'available',\
                           '冻结数量':'frozen',\
                           '在途数量':'un_discharged',\
                           '成本价':'cost',\
                           '盈亏':'profit',\
                           '市值':'Market_value',\
                           '交易市场':'market',\
                           }, inplace=True)
            if isinstance(df_position,type(int())):
                print('df_position 初始化')
            else:
                print('df_position 已更新.')
            df_position = df
            print(df)
        else:
            print('查询结果')
            print(df)
def _recieve_money(content_raw):
    global available_money
    [_,numstr] = content_raw.split(']')
    available_money = float(numstr)
    print('可用资金:%.2f'%available_money)
def _recieve_signal_process(order_raw):
    '''粗交易指令 精细处理'''
    order_list = order_raw.split(',')
    order_prefix_list = order_list[0].split('-')
    # 开始准备所有字段
    order_action = order_prefix_list[0]
    order_code = order_prefix_list[1]
    order_price = order_list[1]
    order_amount = order_list[2]
    # 命令检查
    # 使用的变量
    #print(df_position)
    #print(available_money)
    if order_action == 'BUY':
        # 主要检查 钱够不够
        cli.sendMsg('Q_cash') # 需要临时检查现有资金
        time.sleep(2) # 等待查询结果
        BUY_money = float(order_price) * int(order_amount)
        fee_money = fee.fee(BUY_money,'BUY')
        BUY_money += fee_money['sum']
        if BUY_money < available_money:
            # 钱够
            print('正常收录.'+order_raw)
            pass
        else:
            # 钱不够 改下单全部数量
            new_amount = utility.__rightful_amount_by_amount(available_money/float(order_price))
            if new_amount >= 100:
                print('资金%.2f不足数量变更:%d->%d' % (available_money,int(order_amount),new_amount))
                order_amount = str(new_amount)
            else:
                print('ERROR-资金不足:价格不足以购买100股.' + order_raw)
                return 'ERROR-资金不足:价格不足以购买100股.' + order_raw
    elif order_action == 'SELL':
        # 主要检查 股够不够
        # 主要检查 股有没有买
        try:
            code_list_now = list(df_position['code'].values)
        except:
            code_list_now = []
        if int(order_code) in code_list_now:
            # 实际持仓
            if order_amount == 'ALL':
                new_amount = df_position[df_position['code']==int(order_code)]['available'].values[0]
                print('命令翻译 数量变更:%s->%d' % (order_amount,new_amount))
                order_amount = str(new_amount)
            else:
                print('暂不支持:'+order_raw)
                return 'ERROR-暂不支持:'+order_raw
        else:
            print('模拟持仓命令:'+order_raw)
            return 'ERROR-模拟持仓.' + order_raw
    else:
        return 'ERROR-字段错误.' + order_raw
    # 准备输出
    output = order_action + '-' +\
            order_code + ',' +\
            order_price + ',' +\
            order_amount
    return output
def _preset_order_append(content):
    '''预制指令集 添加'''
    global preset_order_count
    global preset_order_dict
    if content.startswith('ERR'):
        # 出错的指令 添加到特别指令集
        pass
    else:
        preset_order_dict[preset_order_count] = content
        preset_order_count += 1

def _generate_market_order():
    '''市价命令生成器
    目前可以生成的命令:
        1.真实持仓 卖出卖出 市价
        2.真实持仓 卖出一半 市价
        '''
    N = 0
    preset_order_dict_market = {} # 预置指令表 市价交易
    global df_position
    if isinstance(df_position,type(int())):
        return {}
    #dff = surveilance_df[(surveilance_df['cost']>0)&(surveilance_df['sim']=='N')].copy()
    dff = surveilance_df[surveilance_df['cost']>0].copy()
    dff['name'] = dff['code'].apply(tdx_net.get_name)
    code_list = dff['code']
    df_Q = tdx_net.get_security_quotes(code_list) # 获取报价
    sell_price_matrix = df_Q['b1_p']
    dff['sell_Market_price'] = df_Q['b1_p']
    dff['buy_Market_price'] = df_Q['a1_p']
    #print(dff)
    for code in code_list:
        name = tdx_net.get_name(code)
        amount = df_position[df_position['code']==int(code)]
        if len(amount) == 0:
            pass
        else:
            sell_price = dff[dff['code']==code]['sell_Market_price'].values[0]
            buy_price = dff[dff['code']==code]['buy_Market_price'].values[0]
            amount = df_position[df_position['code']==int(code)]['available'].values[0]
            # 生成命令表 并打印
            preset_order_dict_market[N] = 'BUY-'+code+','+str(buy_price)+','+str(amount)
            print(N,'买',code,name,'全仓',buy_price)
            preset_order_dict_market[N+1] = 'SELL-'+code+','+str(sell_price)+','+str(amount)
            print(N+1,'卖',code,name,'全仓',sell_price)
            print('-'*5)
            preset_order_dict_market[N+2] = 'BUY-'+code+','+str(buy_price)+','+str(utility.__rightful_amount_by_amount(amount/2))
            print(N+2,'买',code,name,'半仓',buy_price)
            preset_order_dict_market[N+3] = 'SELL-'+code+','+str(sell_price)+','+str(utility.__rightful_amount_by_amount(amount/2))
            print(N+3,'卖',code,name,'半仓',sell_price)
            print('-'*10)
            N = len(preset_order_dict_market)
    return preset_order_dict_market


def _recieve_signal(order):
    '''收到交易指令信号'''
    print('realtime发来:',order)
    order_content_raw = order.split(':')[-1]
    order_content = _recieve_signal_process(order_content_raw) # 命令解析
    _preset_order_append(order_content)
    pass
def func_set_wrapper():
    '''收信处理 功能组
    只有print()'''
    def func_set(order):
        global heartbeat_recieved
        order_list = order.split('>')
        if order == 'win7_master:HEARTBEAT>[OK]':
            #print(order)
            heartbeat_recieved = True
        elif order_list[-1].startswith('\n'):
            _recieve_dataframe(order)
        elif order_list[-1].startswith('[可用金额]'):
            _recieve_money(order_list[-1])
        elif order_list[0].startswith('realtime_eye'):
            _recieve_signal(order_list[0])
        else:
            print(order,'\n>')
    return func_set

def main():
    '''主进程'''
    global heartbeating
    ser = comm_utility.Server(func_set_wrapper())
    ser.start()
    cli.start()
    ########初始化开始##########
    __init_count = 0
    while isinstance(df_position,type(int())):
        print('第%d次获取数据' %(__init_count+1))
        cli.sendMsg('Q_position')
        __init_count += 1
        time.sleep(1.5)
        if __init_count >= 5 and df_position == 0:
            break
    cli.sendMsg('Q_cash')
    time.sleep(0.5)
    ########初始化结束##########
    heartbeating = heartbeat()
    heartbeating.start()
    check_realtime_eye.start()
    i = os.system('clear') # 打印菜单前先清除屏幕
    _sent_h()

if __name__ == '__main__':
    main()
