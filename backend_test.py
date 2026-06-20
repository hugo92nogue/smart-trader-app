import requests
import sys
import json
from datetime import datetime

class CryptoTradingAPITester:
    def __init__(self, base_url="https://smart-trader-app-16.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def run_test(self, name, method, endpoint, expected_status, data=None, timeout=30):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    resp_data = response.json()
                    if 'data' in resp_data:
                        print(f"   Response has data: {type(resp_data['data'])}")
                        if isinstance(resp_data['data'], list):
                            print(f"   Data length: {len(resp_data['data'])}")
                        elif isinstance(resp_data['data'], dict):
                            print(f"   Data keys: {list(resp_data['data'].keys())}")
                except:
                    print(f"   Response: {response.text[:200]}...")
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:300]}")
                self.failed_tests.append({
                    'name': name,
                    'endpoint': endpoint,
                    'expected': expected_status,
                    'actual': response.status_code,
                    'response': response.text[:500]
                })

            return success, response.json() if response.headers.get('content-type', '').startswith('application/json') else {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.failed_tests.append({
                'name': name,
                'endpoint': endpoint,
                'error': str(e)
            })
            return False, {}

    def test_health(self):
        """Test health endpoint"""
        return self.run_test("Health Check", "GET", "api/health", 200)

    def test_pairs(self):
        """Test trading pairs endpoint"""
        return self.run_test("Trading Pairs", "GET", "api/pairs", 200)

    def test_klines(self, symbol="BTCUSDT"):
        """Test klines endpoint"""
        return self.run_test(f"Klines for {symbol}", "GET", f"api/pairs/{symbol}/klines?interval=1h&limit=200", 200)

    def test_indicators(self, symbol="BTCUSDT"):
        """Test indicators endpoint"""
        return self.run_test(f"Indicators for {symbol}", "GET", f"api/pairs/{symbol}/indicators?interval=1h", 200)

    def test_balance(self):
        """Test account balance"""
        return self.run_test("Account Balance", "GET", "api/account/balance", 200)

    def test_place_order(self):
        """Test placing an order"""
        order_data = {
            "symbol": "BTCUSDT",
            "side": "buy",
            "order_type": "market",
            "quantity": 0.001,
            "mode": "manual"
        }
        return self.run_test("Place Order", "POST", "api/orders", 200, order_data)

    def test_order_history(self):
        """Test order history"""
        return self.run_test("Order History", "GET", "api/orders/history?limit=50", 200)

    def test_ai_analysis(self, symbol="BTCUSDT"):
        """Test AI analysis endpoint"""
        analysis_data = {
            "symbol": symbol,
            "interval": "1h"
        }
        return self.run_test("AI Analysis", "POST", "api/analysis/ai", 200, analysis_data, timeout=60)

    def test_signals(self):
        """Test signals endpoint"""
        return self.run_test("Trading Signals", "GET", "api/signals?limit=50", 200)

    def test_new_listings(self):
        """Test new listings endpoint"""
        return self.run_test("New Listings", "GET", "api/new-listings", 200)

    def test_settings(self):
        """Test settings endpoint"""
        return self.run_test("Settings", "GET", "api/settings", 200)

    def test_auto_trade_toggle(self):
        """Test auto-trade toggle endpoint"""
        # Test enabling auto-trade
        toggle_data = {"enabled": True}
        success1, resp1 = self.run_test("Auto-Trade Enable", "POST", "api/settings/auto-trade", 200, toggle_data)
        
        # Test disabling auto-trade
        toggle_data = {"enabled": False}
        success2, resp2 = self.run_test("Auto-Trade Disable", "POST", "api/settings/auto-trade", 200, toggle_data)
        
        return success1 and success2

    # ═══ FUTURES ENDPOINTS ═══
    def test_futures_balance(self):
        """Test futures balance endpoint"""
        return self.run_test("Futures Balance", "GET", "api/futures/balance", 200)

    def test_futures_positions(self):
        """Test futures positions endpoint"""
        return self.run_test("Futures Positions", "GET", "api/futures/positions", 200)

    def test_futures_history(self):
        """Test futures trade history"""
        return self.run_test("Futures History", "GET", "api/futures/history?limit=50", 200)

    def test_futures_order_long(self):
        """Test opening a LONG futures position"""
        order_data = {
            "symbol": "BTCUSDT",
            "side": "long",
            "action": "open",
            "quantity": 0.001,
            "leverage": 5
        }
        return self.run_test("Futures Order - Open Long", "POST", "api/futures/order", 200, order_data)

    def test_futures_order_short(self):
        """Test opening a SHORT futures position"""
        order_data = {
            "symbol": "BTCUSDT",
            "side": "short",
            "action": "open",
            "quantity": 0.001,
            "leverage": 10
        }
        return self.run_test("Futures Order - Open Short", "POST", "api/futures/order", 200, order_data)

    def test_websocket_connection(self):
        """Test WebSocket connection for real-time prices"""
        import websocket
        import threading
        import time
        
        print(f"\n🔍 Testing WebSocket Connection...")
        
        ws_url = self.base_url.replace('https://', 'wss://').replace('http://', 'ws://') + '/ws/prices'
        print(f"   WebSocket URL: {ws_url}")
        
        self.tests_run += 1
        messages_received = []
        connection_successful = False
        
        def on_message(ws, message):
            try:
                data = json.loads(message)
                messages_received.append(data)
                print(f"   📨 Received: {data.get('type', 'unknown')} for {data.get('symbol', 'N/A')}")
            except Exception as e:
                print(f"   ❌ Message parse error: {e}")
        
        def on_open(ws):
            nonlocal connection_successful
            connection_successful = True
            print(f"   ✅ WebSocket connected")
            # Subscribe to BTCUSDT
            ws.send(json.dumps({"action": "set_symbol", "symbol": "BTCUSDT"}))
        
        def on_error(ws, error):
            print(f"   ❌ WebSocket error: {error}")
        
        def on_close(ws, close_status_code, close_msg):
            print(f"   🔌 WebSocket closed")
        
        try:
            ws = websocket.WebSocketApp(ws_url,
                                      on_open=on_open,
                                      on_message=on_message,
                                      on_error=on_error,
                                      on_close=on_close)
            
            # Run WebSocket in a separate thread
            wst = threading.Thread(target=ws.run_forever)
            wst.daemon = True
            wst.start()
            
            # Wait for connection and messages
            time.sleep(5)
            ws.close()
            
            if connection_successful and len(messages_received) > 0:
                self.tests_passed += 1
                print(f"✅ Passed - WebSocket connected and received {len(messages_received)} messages")
                return True, {"messages": len(messages_received)}
            else:
                print(f"❌ Failed - Connection: {connection_successful}, Messages: {len(messages_received)}")
                self.failed_tests.append({
                    'name': 'WebSocket Connection',
                    'endpoint': '/ws/prices',
                    'error': f"Connection: {connection_successful}, Messages: {len(messages_received)}"
                })
                return False, {}
                
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.failed_tests.append({
                'name': 'WebSocket Connection',
                'endpoint': '/ws/prices',
                'error': str(e)
            })
            return False, {}

def main():
    print("🚀 Starting Crypto Trading API Tests")
    print("=" * 50)
    
    tester = CryptoTradingAPITester()
    
    # Test basic endpoints first
    print("\n📊 Testing Basic Endpoints...")
    tester.test_health()
    tester.test_settings()
    tester.test_auto_trade_toggle()
    
    # Test market data endpoints
    print("\n📈 Testing Market Data Endpoints...")
    tester.test_pairs()
    tester.test_klines()
    tester.test_indicators()
    
    # Test account endpoints
    print("\n💰 Testing Account Endpoints...")
    tester.test_balance()
    
    # Test trading endpoints
    print("\n🔄 Testing Trading Endpoints...")
    tester.test_place_order()
    tester.test_order_history()
    
    # Test futures endpoints
    print("\n🚀 Testing Futures Endpoints...")
    tester.test_futures_balance()
    tester.test_futures_positions()
    tester.test_futures_history()
    tester.test_futures_order_long()
    tester.test_futures_order_short()
    
    # Test WebSocket
    print("\n🌐 Testing WebSocket...")
    tester.test_websocket_connection()
    
    # Test analysis endpoints
    print("\n🧠 Testing Analysis Endpoints...")
    tester.test_signals()
    tester.test_new_listings()
    
    # Test AI analysis (might be slow)
    print("\n🤖 Testing AI Analysis...")
    tester.test_ai_analysis()
    
    # Print results
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} passed")
    
    if tester.failed_tests:
        print(f"\n❌ Failed Tests ({len(tester.failed_tests)}):")
        for test in tester.failed_tests:
            error_msg = test.get('error', f"Status {test.get('actual')} != {test.get('expected')}")
            print(f"  - {test['name']}: {error_msg}")
    
    success_rate = (tester.tests_passed / tester.tests_run * 100) if tester.tests_run > 0 else 0
    print(f"\n✅ Success Rate: {success_rate:.1f}%")
    
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())