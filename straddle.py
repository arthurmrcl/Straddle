import pandas as pd
import numpy as np
from datetime import *
import time as tm
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import *
import threading

class IBapi(EWrapper, EClient):                                                 #Création de la classe IB API
    def __init__(self):         
        EClient.__init__(self, self)
        self.quotes = []
        self.conIdContract = 0                                              
        self.strikes = []
        self.expirations = []                                                   # Initialisation des variables
        self.price = 0
        self.capital = 100000
        self.all_positions = pd.DataFrame([], columns=['Account', 'Symbol', 'Quantity', 'Average Cost', 'Sec Type',
                                                        'Combo Legs Descrip', 'Expiry','Right','Strike','ID'])

    def contractDetails(self, reqId, contractDetails):
        self.conIdContract = contractDetails.contract.conId                     # stock le contrat ID

    def nextValidId(self, orderId: int):
        super().nextValidId(orderId)                                            # Récupère les ordres transmis  
        self.nextorderId = orderId

    def tickPrice(self, reqId, tickType, price, attrib):
        if tickType == 2 and reqId == 1:                                       
            self.price = price                                                  # Récupère le prix
			
    def historicalData(self, reqId, bar):
        self.quotes.append([bar.date, bar.close])                              # Télécharge les cours de clôture
    
    def OptionParameter(self, reqId, exchange, underlyingConId, tradingClass, multiplier, expirations, strikes):
            self.strikes.extend(strikes)                                       # Récupère la liste des strike et la liste des dates de maturité
            self.expirations.extend(expirations)

    def position(self, account, contract, pos, avgCost):
        index = str(account)+str(contract.symbol)                              # Récupère l'ensemble des positions
        self.all_positions.loc[index]= account, contract.symbol, pos, avgCost, contract.secType, contract.comboLegsDescrip, contract.lastTradeDateOrContractMonth, contract.right, contract.strike, contract.secId


def Is_Connected():
    while not app.isConnected():                                                #Tant que la connexion n'est pas établie, essayer de la rétablir
        try:
            app.connect('127.0.0.1',7496,123)
            api_thread = threading.Thread(target=run_loop, deamon=True)         # Parralélisme de l'exécution du programme et de l'API
            api_thread.start()
            tm.sleep(5)         
        except:
            tm.sleep(2)
            print("Erreur de connexion")


def run_loop():                                                               # Fonction utile pour le parralélisme
	app.run()

def Control_Hour(time1,time2):
    today = datetime.today()
    now = datetime.now()
    if date.weekday(today) < 6:                                               # Si jour ouvré
        return ((time1 < now) and (now < time2))                              # Renvoie si maintenant est compris entre les deux dates
    else: 
        return False
         
def Recup_List(chemin,day_before):
    today = datetime.today()
    date_earning = today + pd.tseries.offsets.BDay(day_before)                                          # Renvoie à la prochaine date ouvrée selon le paramètre day_before
    list_action = pd.read_csv(chemin,index_col=0)                                                       # Télécharger le calendrier d'earning report
    list_action = list_action.loc[list_action["reportDate"]==date_earning]
    list_action = list_action.loc[list_action["currency"]=="USD"]
    return list_action, date_earning                                                                    # Renvoyer la liste uniquement avec à la date choisie

class Straddle(symbol,date_report, day_max):
    def __init__(self, symbol,date_report,day_max):
        self.underlying = Contract()
        self.underlying.symbol = symbol
        self.underlying.secType = 'STK'                                                                 # crée les variables de bases de la classe straddle
        self.underlying.exchange = 'SMART'
        self.underlying.currency = 'USD'
        self.ref_date = date_report
        self.bdday_max = day_max

    def Recup_quotes(self):
        Is_Connected()
        app.reqMarketDataType(3)
        app.reqHistoricalData(1,self.underlying, '', '1 Y',                                             # Télécharge les cotations sur un an
                                       '1 day','BID', 0, 2, False, [])                                  # Time format = 2, car plus facile à convertir en datetime par la suite
        tm.sleep(2)
        self.quotes = pd.DataFrame(app.quotes, columns=['Datetime','Close'])
        self.quotes["Datetime"] = pd.to_datetime(self.quotes["Datetime"],unit='s')                      # Converti la colonne Date
        self.last_quote = self.quotes["Close"].iloc[-1]                                                 # Prix "Spot"
        self.vol = self.quotes["Close"].pct_change().std()                                              # Volatilité, qui sera utilisée pour la pondération
        
        app.quotes.clear()
        return self.last_quote, self.vol
    
    def Option_picking(self):
        Is_Connected()

        app.reqContractDetails(1,self.underlying)                                                           # Récupérer le ReqId
        tm.sleep(2)

        app.reqSecDefOptParams(1, self.underlying.symbol, "", "STK",app.conIdContract)
        tm.sleep(2)

        expirations = [datetime.strptime(expiration,'%Y%m%d') for expiration in app.expirations]            # Converti les dates sous le bon format
        self.strike = min(app.strikes, key=lambda s: abs(s -self.last_quote))                               # Trouver le strike le plus proche de notre spot
        date_cible = self.ref_date + pd.tseries.offsets.BDay(self.bdday_max)                                # maturité optimale
        self.maturity = min(expirations, key=lambda exp: abs(exp -date_cible))                              # Date de maturité réelle la plus proche
        app.strikes.clear()
        app.expirations.clear()

        self.price = []
        for right in ["C","¨P"]:
            opt = Contract()                                                                                # Récypère le prix du call et du put à l'achat
            opt.secType = 'OPT'
            opt.exchange = "SMART"
            opt.currency = "USD"
            opt.symbol = self.underlying.symbol
            opt.right = right
            opt.lastTradeDateOrContractMonth = maturity.strftime("%y%m%d")
            opt.strike = self.strike
            opt.multiplier = '10'
            app.reqContractDetails(1,opt)
            tm.sleep(1)
            app.reqMktData(app.conIdContract)
            tm.sleep(1)
            self.price.append(app.price)                                                                    

        return self.price[1], self.price[0], self.strike, self.maturity                                    # Retourne les éléments nécessaires pour la suite
    
    def Decision(self):
        risque = (self.price[1] + self.price[0]) / self.strike 
        if ((self.vol/risque) > 0.51) and (vol > 0.03):                                                   # Les valeurs décisions sont issues de recherche pendant le Backtest
            return True
        else:
            return False
        
def Investing(liste,capital):
    liste = liste.sort_values("vol",ascending=False)
    if len(liste) > 5:
        liste = liste.iloc[:5]                                                                             # Ne garde que les 5 plus grandes valeurs
    for i in range(len(liste)):
        symbol = liste.index[i]                                                             
        strike = liste["strike"].iloc[i]
        date_opt = liste["maturity"].iloc[i]
        weight = liste["vol"].iloc[i] / liste["vol"].sum()                                                # Choix d'une pondération simple par volume, issu des recherches du backtest
        volume = round(((weight*capital)/((liste["put"].iloc[i] + liste["call"].iloc[i])*10)),0)          # Calcul le volume à acheter
        if volume >= 1: 
            for right in ["C","P"]:                                                                     # Achat d'un call et d'un put
                try:
                    Is_Connected()

                    opt = Contract()
                    opt.symbol = symbol
                    opt.secIdType = "OPT"
                    opt.currency = "USD"
                    opt.exchange = "SMART"
                    opt.right = right                                                                   # Définition des options 
                    opt.multiplier = '10'
                    opt.strike = strike
                    opt.lastTradeDateOrContractMonth = date_opt.strftime("%y%m%d")
                    opt.comboLegsDescrip = '125'                                                        # Permet d'indiquer les positions issues de notre algorithme

                    order = Order()
                    order.action = 'BUY'                                                               # Définition de l'ordre d'achat
                    order.totalQuantity = int(volume)
                    order.orderType = 'MKT'
                    order.transmit = True

                    app.placeOrder(app.nextorderId, opt, order)                                        # Placement de l'ordre
                    app.nextorderId += 1
                except:
                    pass

def Recup_Pos():
    Is_Connected()
    app.reqPositions()
    time.sleep(2)
    positions = app.all_positions
    positions = positions.loc[positions["Combo Legs Descrip"]== '125']                              # Filtre sur les positions ouvertes par l'algorithme
    positions = positions.loc[positions['Sec Type']=='OPT']
    positions = positions.loc[positions["Expiry"]]                                                  # Options avec comme maturité aujourd'hui
    positions['Expiry'] = positions["Expiry"].apply(lambda x: datetime.strptime(x,'%Y%m%d'))        
    positions = positions.loc[positions["Expiry"] == datetime.today()]
    return positions

def Close_Pos(positions):
    Is_Connected()
    for i in range(len(positions)):                                                                # Pour chaque option prenant fin aujourd'hui...
        account = positions["Account"].iloc[i]
        symbol = positions["Symbol"].iloc[i]
        quantity = positions["Quantity"].iloc[i]
        right = positions["Right"].iloc[i]                                                         # On récupère les infos de la position
        expiry = positions["Expiry"].iloc[i].strftime("%y%m%d")
        secid = positions["ID"].iloc[i]
        strike = positions["Strike"].iloc[i]
        prime = positions["Average Cost"].iloc[i]

        opt = Contract()
        opt.symbol = symbol
        opt.secType = "OPT"
        opt.secId = secid                                                                        # on reproduit le contrat
        opt.right = right
        opt.exchange = "SMART"
        opt.currency = "USD"
        opt.lastTradeDateOrContractMonth = expiry
        opt.strike = strike

        underlying = Contract()
        underlying.symbol = symbol                                                              # on crée un contrat pour le sous-jacent, afin de fermer la position du SJ si on exerce l'option
        underlying.exchange = "SMART"
        underlying.currency = "USD"

        app.reqContractDetails(1,underlying)
        tm.sleep(1)
        app.reqMktData(app.conIdContract)                                                       # Récupération du prix spot à la clôture
        tm.sleep(1)
        spot = app.price

        order = Order()
        order.orderType = "MKT"                                                                 # On prépare l'ordre de fermeture du SJ 
        order.totalQuantity = quantity

        if right == "C":                                                                        # Si la position est un call
            pay_off = spot - strike - prime                                                     # Calcul du gain de la position
            app.capital = app.capital + (pay_off * quantity)                                    # Ajout du gain au capital, ce qui permet de capitaliser les gains
            if spot > strike:                                                                   # Si position supérieur au spot:
                app.exerciseOptions(app.nextorderId, opt, quantity, 1, account, 1)              #   on exerce l'option
                order.action = "SELL"
                order.action = "BUY"
                tm.sleep(10)
                order.transmit = True                                                           # On vend le sous-jacent
                tm.sleep(1)
                app.placeOrder(app.nextorderId, underlying, order)
            else: 
                pass
        elif right == "P":                                                                      # Si postion est un put
            pay_off = strike - spot - prime                                                     
            app.capital = app.capital + (pay_off * quantity)           
            if spot < strike:
                app.exerciseOptions(app.nextorderId, opt, quantity, 1, account, 1)
                order.action = "BUY"
                tm.sleep(10)
                order.transmit = True
                tm.sleep(1)                                                                   # On achète le sous-jacent
                app.placeOrder(app.nextorderId, underlying, order)
            else: 
                pass
        
chemin = "X\\XX\\Algorithm\\calendar_data_algo.csv"                             # Fichier CSV, regarder calendar-strapping.py
day_before = 5
day_max_after = 5                                                               # En jours ouvrés
app = IBapi()                                                                   # Création d'un objet IB API

if __name__ == "__main__":
    while True:
        if Control_Hour(time(15,0),time(15,30)):
            """
            Récupère la liste des sociétés américaines déclarant leurs résultats aujourd'hui
            """
            if not liste_usd:
                liste_usd, date_report = Recup_List(chemin)
                liste_usd[["strike","maturity","call","put","vol","weight"]] = np.nan
                liste_usd = liste_usd.iloc[liste_usd["currency"]=="USD"]
                
        if Control_Hour(time(15,35),time(20,45)):
            """
            Application de la stratégie Straddle Earning Announcement
            """
            if liste_usd:
                for i in range(len(liste_usd)):
                    symbol = liste_usd.index[i]
                    contract = Straddle(symbol,date_report,day_max_after)
                    try:
                        quote, vol = contract.Recup_quotes()
                        put, call, strike, maturity = contract.Option_picking()
                        if contract.Decision() is False:
                            liste_usd.drop([0],inplace=True)
                        else:
                            liste_usd["strike"].iloc[i] = strike
                            liste_usd["maturity"].iloc[i] = maturity
                            liste_usd["call"].iloc[i] = call
                            liste_usd["put"].iloc[i] = put
                            liste_usd["vol"].iloc[i] = vol
                    except:
                        liste_usd.drop([0],inplace=True)
                Investing(liste_usd, (app.capital/(day_before + day_max_after)))
                del liste_usd,symbol, vol, call, put, quote, maturity, date_report
    
        if Control_Hour(time(20,45),time(21,30)):
            """
            Execution des options dans la monnaie ayant comme maturité aujourd'hui 
            """
            try:
                positions_usd = Recup_Pos()
                if positions_usd:
                    Close_Pos(positions_usd)
                    del positions_usd
            except:
                pass
        
        tm.sleep(60)
