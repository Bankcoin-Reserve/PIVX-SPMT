#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sqlite3
import threading

from constants import user_dir, database_File, trusted_RPC_Servers, DEFAULT_MN_CONF
from misc import printDbg, getCallerName, getFunctionName, printException, add_defaultKeys_to_dict


class Database():
    
    '''
    class methods
    '''
    def __init__(self, app):
        self.app = app
        self.file_name = database_File
        self.lock = threading.Lock()
        self.isOpen = False
        self.conn = None
        
        
    
    def open(self):
        if not self.isOpen:
            printDbg("trying to open database...")
            self.lock.acquire()
            try:
                if self.conn is None:
                    self.conn = sqlite3.connect(self.file_name)
                
                self.initTables()
                self.conn.commit()
                self.conn.close()
                self.conn = None
                self.isOpen = True
                printDbg("Database open")

            except Exception as e:
                err_msg = 'SQLite initialization error'
                printException(getCallerName(), getFunctionName(), err_msg, e.args)
                
            finally:
                self.lock.release()
                
        else:
            raise Exception("Database already open")
        
        
            
    def close(self):
        if self.isOpen:
            printDbg("trying to close database...")
            self.lock.acquire()
            try:
                if self.conn is not None:
                    self.conn.close()
                    
                self.conn = None
                self.isOpen = False
                printDbg("Database closed")
                
            except Exception as e:
                err_msg = 'SQLite closing error'
                printException(getCallerName(), getFunctionName(), err_msg, e.args)
                
            finally:
                self.lock.release()
        
        else:
            err_msg = "Database already closed"
            printException(getCallerName(), "close()", err_msg, "")
        
        
        
    def getCursor(self):
        if self.isOpen:
            self.lock.acquire()
            try:
                if self.conn is None:
                    self.conn = sqlite3.connect(self.file_name)
                return self.conn.cursor()
            
            except Exception as e:
                err_msg = 'SQLite error getting cursor'
                printException(getCallerName(), getFunctionName(), err_msg, e.args)
                self.lock.release()
                
        else:
            raise Exception("Database closed")
        
        
    def releaseCursor(self, rollingBack=False):
        if self.isOpen:
            try:
                if self.conn is not None:
                    # commit
                    if rollingBack:
                        self.conn.rollback()
                    
                    else:
                        self.conn.commit()
                    
                    # close connection
                    self.conn.close()
                        
                self.conn = None
                    
            except Exception as e:
                err_msg = 'SQLite error releasing cursor'
                printException(getCallerName(), getFunctionName(), err_msg, e.args)
                
            finally:
                self.lock.release()
        
        else:
            raise Exception("Database closed")

        
        
    def initTables(self):
        try:
            cursor = self.conn.cursor()
            
            # Tables for RPC Servers
            cursor.execute("CREATE TABLE IF NOT EXISTS PUBLIC_RPC_SERVERS("
                           " id INTEGER PRIMARY KEY, protocol TEXT, host TEXT,"
                           " user TEXT, pass TEXT)")
            
            cursor.execute("CREATE TABLE IF NOT EXISTS CUSTOM_RPC_SERVERS("
                           " id INTEGER PRIMARY KEY, protocol TEXT, host TEXT,"
                           " user TEXT, pass TEXT)")
            
            self.initTable_RPC(cursor)
            
            # Tables for Masternodes
            cursor.execute("CREATE TABLE IF NOT EXISTS MASTERNODES("
                        " name TEXT PRIMARY KEY, ip TEXT, port INTEGER, mnPrivKey TEXT,"
                        " hwAcc INTEGER, isTestnet INTEGER, isHardware INTEGER,"
                        " address TEXT, spath INTEGER, pubkey TEXT, txid TEXT, txidn INTEGER)")

            
        except Exception as e:
            err_msg = 'error initializing tables'
            printException(getCallerName(), getFunctionName(), err_msg, e.args)
    
    
    
    def initTable_RPC(self, cursor):
        s = trusted_RPC_Servers
        # Insert Default public trusted servers
        cursor.execute("INSERT OR REPLACE INTO PUBLIC_RPC_SERVERS VALUES"
                       " (?, ?, ?, ?, ?),"
                       " (?, ?, ?, ?, ?),"
                       " (?, ?, ?, ?, ?);",
                       (0, s[0][0], s[0][1], s[0][2], s[0][3],
                        1, s[1][0], s[1][1], s[1][2], s[1][3],
                        2, s[2][0], s[2][1], s[2][2], s[2][3]))
        
        # Insert Local wallet
        cursor.execute("INSERT OR IGNORE INTO CUSTOM_RPC_SERVERS VALUES"
                       " (?, ?, ?, ?, ?);",
                       (0, "http", "127.0.0.1:51473", "rpcUser", "rpcPass"))

    
    
    '''
    General methods
    '''  
    def clearTable(self,  table_name):
        try:
            cursor = self.getCursor()
            cursor.execute("DELETE FROM %s" % table_name)
            # in case, reload default RPC and emit changed signal
            if table_name == 'CUSTOM_RPC_SERVERS':
                self.initTable_RPC(cursor)
                self.app.sig_changed_rpcServers.emit()
            
        except Exception as e:
            err_msg = 'error clearing %s in database' % table_name
            printException(getCallerName(), getFunctionName(), err_msg, e.args)
   
        finally:
            self.releaseCursor()
                
        
        
        
    '''
    RPC servers methods
    '''
    def addRPCServer(self, protocol, host, user, passwd):
        try:
            cursor = self.getCursor()

            cursor.execute("INSERT INTO CUSTOM_RPC_SERVERS (protocol, host, user, pass) "
                           "VALUES (?, ?, ?, ?)",
                           (protocol, host, user, passwd)
                           )
            
        except Exception as e:
            err_msg = 'error adding RPC server entry to DB'
            printException(getCallerName(), getFunctionName(), err_msg, e.args)      
        finally:
            self.releaseCursor()
        
        self.app.sig_changed_rpcServers.emit()
        
        
        
    def editRPCServer(self, protocol, host, user, passwd, id):
        try:
            cursor = self.getCursor()

            cursor.execute("UPDATE CUSTOM_RPC_SERVERS "
                           "SET protocol = ?, host = ?, user = ?, pass = ?"
                           "WHERE id = ?",
                           (protocol, host, user, passwd, id)
                           )
                    
        except Exception as e:
            err_msg = 'error editing RPC server entry to DB'
            printException(getCallerName(), getFunctionName(), err_msg, e.args)       
        finally:
            self.releaseCursor()   
        
        self.app.sig_changed_rpcServers.emit()
        
        
        
    def getRPCServers(self, custom, id=None):
        tableName = "CUSTOM_RPC_SERVERS" if custom else "PUBLIC_RPC_SERVERS"
        try:
            cursor = self.getCursor()
            if id is None:
                cursor.execute("SELECT * FROM %s" % tableName)
            else:
                cursor.execute("SELECT * FROM %s WHERE id = ?" % tableName, (id,))
            rows = cursor.fetchall()
            
        except Exception as e:
            err_msg = 'error getting RPC servers from database'
            printException(getCallerName(), getFunctionName(), err_msg, e.args)
            rows = []     
        finally:
            self.releaseCursor() 
        
        server_list = []
        for row in rows:
            server = {}
            server["id"] = row[0]
            server["protocol"] = row[1]
            server["host"] = row[2]
            server["user"] = row[3]
            server["password"] = row[4]
            server["isCustom"] = custom
            server_list.append(server)
        
        if id is not None:
            return server_list[0]
        
        return server_list
        
            
    
    def removeRPCServer(self, index):
        try:
            cursor = self.getCursor()
            cursor.execute("DELETE FROM RPC_SERVERS"
                           " WHERE id=?", (index,))
            
        except Exception as e:
            err_msg = 'error removing RPC servers from database'
            printException(getCallerName(), getFunctionName(), err_msg, e.args)
   
        finally:
            self.releaseCursor()
            
        self.app.sig_changed_rpcServers.emit()
            
        
        
    '''
    Masternode methods
    '''
    def getMasternodeList(self):
        try:
            cursor = self.getCursor()

            cursor.execute("SELECT * FROM MASTERNODES")
            rows = cursor.fetchall()
            
        except Exception as e:
            err_msg = 'error getting masternode list'
            printException(getCallerName(), getFunctionName(), err_msg, e.args)
            rows = []       
        finally:
            self.releaseCursor() 
        
        mnlist = []
        
        for row in rows:
            # fetch masternode item
            new_masternode = {}
            new_masternode['name'] = row[0]
            new_masternode['ip'] = row[1]
            new_masternode['port'] = row[2]
            new_masternode['mnPrivKey'] = row[3]
            new_masternode['hwAcc'] = row[4]
            new_masternode['isTestnet'] = row[5]
            new_masternode['isHardware'] = (row[6] > 0)          
            coll = {}
            coll['address'] = row[7]
            coll['spath'] = row[8]
            coll['pubKey'] = row[9]
            coll['txid'] = row[10]
            coll['txidn'] = row[11]
            new_masternode['collateral'] = coll
            # add to list
            mnlist.append(new_masternode)
        
        return mnlist

     
            
    def addNewMasternode(self, mn):
        try:
            cursor = self.getCursor()

            cursor.execute("INSERT INTO MASTERNODES(name, ip, port, mnPrivKey,"
                           " hwAcc, isTestnet, isHardware,  address, spath, pubkey, txid, txidn) "
                           "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                           (mn['name'], mn['ip'], mn['port'], mn['mnPrivKey'], mn['hwAcc'], mn['isTestnet'], 
                            1 if mn['isHardware'] else 0, 
                            mn['collateral'].get('address'), mn['collateral'].get('spath'), 
                            mn['collateral'].get('pubKey'), mn['collateral'].get('txid'), mn['collateral'].get('txidn'))
                           )
            
        except Exception as e:
            err_msg = 'error writing new masternode to DB'
            printException(getCallerName(), getFunctionName(), err_msg, e.args)
        finally:
            self.releaseCursor() 
            
    
    
    def addMasternode(self, mn, old_mn=None):
        add_defaultKeys_to_dict(mn, DEFAULT_MN_CONF)
        
        if not old_mn is None:
            try:
                cursor = self.getCursor()
    
                cursor.execute("UPDATE MASTERNODES "
                               "SET name = ?, ip = ?, port = ?, mnPrivKey = ?, hwAcc = ?, isTestnet = ?, isHardware = ?,"
                               "    address = ?, spath = ?, pubkey = ?, txid = ?, txidn = ?"
                               "WHERE name = ?",
                               (mn['name'], mn['ip'], mn['port'], mn['mnPrivKey'], mn['hwAcc'], mn['isTestnet'], 
                                1 if mn['isHardware'] else 0,  
                                mn['collateral'].get('address'), mn['collateral'].get('spath'), 
                                mn['collateral'].get('pubKey'), mn['collateral'].get('txid'), mn['collateral'].get('txidn'),
                                old_mn['name'])
                               )
                
            except Exception as e:
                err_msg = 'error writing masternode to DB'
                printException(getCallerName(), getFunctionName(), err_msg, e.args)                
            finally:
                self.releaseCursor() 
                
        else:
            # Add new record to the table
            self.addNewMasternode(mn)
            

            
    def deleteMasternode(self, mn_name):
        try:
            cursor = self.getCursor()
            cursor.execute("DELETE FROM MASTERNODES WHERE name = ? ", (mn_name,))
            
        except Exception as e:
            err_msg = 'error deleting masternode from DB'
            printException(getCallerName(), getFunctionName(), err_msg, e.args)
        finally:
            self.releaseCursor() 
            
            
                