# Smart Attendance - ESP32 Fingerprint Client
# Hardware: ESP32-DevKit v1 + R305 (or GT-521F52) + SSD1306 OLED + buzzer + enroll button

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Adafruit_Fingerprint.h>
#include <Adafruit_SSD1306.h>

#define RX_PIN 16   // ESP32 RX2 -> Sensor TX
#define TX_PIN 17   // ESP32 TX2 -> Sensor RX
#define ENROLL_BTN 0
#define BUZZER_PIN 27

// Display
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire);

// Fingerprint sensor on UART2
HardwareSerial fingerSerial(2);
Adafruit_Fingerprint finger(&fingerSerial);

// Wi-Fi / Backend
const char* WIFI_SSID = "CHANGE_ME";
const char* WIFI_PASS = "CHANGE_ME";
const char* BACKEND = "http://192.168.1.50:5000"; // Flask host
const char* DEVICE_ID = "esp32-lab-01";

// Utils
void beep(bool ok = true) {
  const uint16_t toneHz = ok ? 2000 : 400;
  tone(BUZZER_PIN, toneHz, 120);
}

void showMsg(const String& l1, const String& l2 = "") {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println(l1);
  if (l2.length()) display.println(l2);
  display.display();
}

bool postJson(const String& path, DynamicJsonDocument& doc) {
  HTTPClient http;
  String url = String(BACKEND) + path;
  String payload;
  serializeJson(doc, payload);

  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(payload);
  http.end();
  return code >= 200 && code < 300;
}

int fetchNextFingerId() {
  HTTPClient http;
  http.begin(String(BACKEND) + "/api/finger/next-id");
  int code = http.GET();
  if (code != 200) { http.end(); return -1; }
  DynamicJsonDocument doc(128);
  deserializeJson(doc, http.getString());
  http.end();
  return doc["next_id"] | -1;
}

bool enrollFinger() {
  showMsg("Enroll mode", "Press finger");
  while (finger.getImage() != FINGERPRINT_OK) { delay(50); }
  if (finger.image2Tz(1) != FINGERPRINT_OK) { showMsg("Bad image"); return false; }

  showMsg("Lift finger");
  delay(1500);
  showMsg("Press again");
  while (finger.getImage() != FINGERPRINT_OK) { delay(50); }
  if (finger.image2Tz(2) != FINGERPRINT_OK) { showMsg("Mismatch"); return false; }

  if (finger.createModel() != FINGERPRINT_OK) { showMsg("Model fail"); return false; }

  int fid = fetchNextFingerId();
  if (fid < 0) { showMsg("ID error"); return false; }

  if (finger.storeModel(fid) != FINGERPRINT_OK) { showMsg("Store fail"); return false; }

  // Optional: upload template for backup/audit
  String tplHex = "";
  if (finger.getModel() == FINGERPRINT_OK) {
    const size_t tplSize = sizeof(finger.templateBuffer);
    tplHex.reserve(tplSize * 2);
    const char hex[] = "0123456789ABCDEF";
    for (size_t i = 0; i < tplSize; i++) {
      tplHex += hex[finger.templateBuffer[i] >> 4];
      tplHex += hex[finger.templateBuffer[i] & 0x0F];
    }
  }

  DynamicJsonDocument doc(2048);
  doc["name"] = String("User-") + fid; // replace with real name from your admin app
  doc["finger_id"] = fid;
  if (tplHex.length()) doc["template_hex"] = tplHex;
  postJson("/api/finger/enroll", doc);

  showMsg("Enrolled", String("ID ") + fid);
  beep(true);
  delay(1200);
  return true;
}

bool punchOnce() {
  if (finger.getImage() != FINGERPRINT_OK) return false; // no finger
  if (finger.image2Tz() != FINGERPRINT_OK) { showMsg("Bad scan"); beep(false); return true; }
  if (finger.fingerFastSearch() != FINGERPRINT_OK) { showMsg("Access denied"); beep(false); return true; }

  int fid = finger.fingerID;
  showMsg("Match", String("ID ") + fid);

  DynamicJsonDocument doc(256);
  doc["finger_id"] = fid;
  doc["device_id"] = DEVICE_ID;
  doc["action"] = "check_in"; // or "check_out" if you wire a toggle

  if (postJson("/api/finger/check", doc)) {
    beep(true);
  } else {
    beep(false);
  }
  delay(800);
  return true;
}

void setup() {
  pinMode(ENROLL_BTN, INPUT_PULLUP);
  pinMode(BUZZER_PIN, OUTPUT);

  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  display.setTextWrap(true);
  showMsg("Booting...");

  fingerSerial.begin(57600, SERIAL_8N1, RX_PIN, TX_PIN);
  if (!finger.verifyPassword()) {
    showMsg("Sensor error");
    while (true) { delay(1000); }
  }

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  showMsg("WiFi...", WIFI_SSID);
  while (WiFi.status() != WL_CONNECTED) { delay(200); }
  showMsg("WiFi OK", WiFi.localIP().toString());
  beep(true);
}

void loop() {
  if (digitalRead(ENROLL_BTN) == LOW) {
    enrollFinger();
    delay(500);
  }
  punchOnce();
}
