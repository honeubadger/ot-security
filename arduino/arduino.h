#include <LiquidCrystal.h>
#include <Keypad.h>
#include <math.h>

// ============================================
// OT/ICS CYBERSECURITY CONTROLLER V5
//
// ============================================

// ============================================
// LCD1602A
// ============================================

LiquidCrystal lcd(12, 11, 5, 4, 3, 2);

// ============================================
// KEYPAD 4x4
// ============================================

const byte ROWS = 4;
const byte COLS = 4;

char keys[ROWS][COLS] = {
  {'1', '2', '3', 'A'},
  {'4', '5', '6', 'B'},
  {'7', '8', '9', 'C'},
  {'*', '0', '#', 'D'}
};

byte rowPins[ROWS] = {6, 7, 8, 13};
byte colPins[COLS] = {A0, A1, A2, A3};

Keypad keypad = Keypad(
  makeKeymap(keys),
  rowPins,
  colPins,
  ROWS,
  COLS
);

// ============================================
// MOTOR CONFIGURATION
// ============================================

const byte motorPin =  9;

int motorSpeed = 100;

const int minSpeed = 50;
const int maxSpeed = 100;

bool motorRunning = false;

// ============================================
// BUZZER
// ============================================

const byte buzzerPin = 10;

bool alarmActive = false;
bool securityAlert = false;
unsigned long buzzerStartTime = 0;
const unsigned long BUZZER_DURATION = 3000;
bool buzzerTimerActive = false;

// ============================================
// TEMPERATURE SENSOR
// ============================================

const byte thermistorPin = A4;

const float SERIES_RESISTOR = 10000.0;
const float NOMINAL_RESISTANCE = 10000.0;
const float NOMINAL_TEMPERATURE = 25.0;
const float BETA = 3950.0;

float temperatureC = NAN;
float temperatureF = NAN;

const float MAX_TEMPERATURE_F = 90.0;
const float RESET_TEMPERATURE_F = 88.0;
bool overheatDetected = false; // block until reset manual


// ============================================
// SYSTEM VARIABLES
// ============================================

// 0 = Main
// 1 = Motor
// 2 = Sensors
// 3 = Security
// 4 = Alarm

byte currentMenu = 0;

unsigned long lastSensorUpdate = 0;
unsigned long lastLCDUpdate = 0;

const unsigned long SENSOR_INTERVAL = 2000;
const unsigned long LCD_INTERVAL = 1000;

// ============================================
// MOTOR CONTROL
// ============================================

void updateMotor() {

  int pwm = 0;

  if (overheatDetected) {
    motorRunning = false;
  } else if (motorRunning) {

    pwm = map(
      motorSpeed,
      0,
      100,
      0,
      255
    );
  }

  analogWrite(motorPin, pwm);

  Serial.print("PWM:");
  Serial.println(pwm);
}

// ============================================
// TEMPERATURE READING
// ============================================

float readTemperature() {

  int adc = analogRead(thermistorPin);

  if (adc <= 0 || adc >= 1023) {
    return NAN;
  }

  // NTC connected to 5V
  // 10k resistor connected to GND

  float resistance =
      SERIES_RESISTOR * (1023.0 / adc - 1.0);

  float steinhart =
      resistance / NOMINAL_RESISTANCE;

  steinhart = log(steinhart);

  steinhart /= BETA;

  steinhart +=
      1.0 / (NOMINAL_TEMPERATURE + 273.15);

  steinhart = 1.0 / steinhart;

  steinhart -= 273.15;

  return steinhart;
}

// ============================================
// MAIN MENU
// ============================================

void showMenu() {

  currentMenu = 0;

  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.print("A:MOTOR B:SENSOR");

  lcd.setCursor(0, 1);
  lcd.print("C:SECURITY D:CFG");
}

// ============================================
// MOTOR MENU
// ============================================

void showMotorMenu() {

  currentMenu = 1;

  lcd.clear();

  lcd.setCursor(0, 0);

  lcd.print("MOTOR: ");

  if (motorRunning) {
    lcd.print("ON");
  } else {
    lcd.print("OFF");
  }

  lcd.setCursor(0, 1);

  lcd.print("SPEED: ");
  lcd.print(motorRunning ? motorSpeed : 0);
  lcd.print("%");
}

// ============================================
// SENSOR MENU
// ============================================

void showSensorMenu() {

  currentMenu = 2;

  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.print("TEMPERATURE");

  lcd.setCursor(0, 1);

  if (isnan(temperatureF)) {
    lcd.print("SENSOR ERROR");
  } else {
    lcd.print("TEMP: ");
    lcd.print(temperatureF, 1);
    lcd.print(" F");
  }
}

// ============================================
// SECURITY MENU
// ============================================

void showSecurityMenu() {

  currentMenu = 3;

  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.print("CYBERSECURITY");

  lcd.setCursor(0, 1);

  if (securityAlert) {
    lcd.print("ALERT DETECTED");
  } else {
    lcd.print("SYSTEM NORMAL");
  }
}

// ============================================
// ALARM MENU
// ============================================

void showAlarmMenu() {

  currentMenu = 4;

  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.print("ALARM SETTINGS");

  lcd.setCursor(0, 1);
  lcd.print("1:ON  2:OFF");
}

// ============================================
// ACTIVATE ALARM
// ============================================

void activateAlarm() {

  alarmActive = true;
  securityAlert = true;

  digitalWrite(buzzerPin, HIGH);
  buzzerStartTime = millis();
  buzzerTimerActive = true;

  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.print("SECURITY ALERT!");

  lcd.setCursor(0, 1);
  lcd.print("BUZZER ACTIVE");

  Serial.println("ALARM ACTIVATED");
}

// ============================================
// DEACTIVATE ALARM
// ============================================

void deactivateAlarm() {

  if (overheatDetected) {
    Serial.println("ERROR:THERMAL_LOCK");
    return;
  }

  alarmActive = false;
  buzzerTimerActive = false;

  // Keep securityAlert true until manually reset
  digitalWrite(buzzerPin, LOW);

  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.print("ALARM SILENCED");

  lcd.setCursor(0, 1);
  lcd.print("SYSTEM RUNNING");

  Serial.println("ALARM DEACTIVATED");
}

// ============================================
// SERIAL COMMAND VALIDATION
// ============================================

bool validNumber(String value) {

  if (value.length() == 0) {
    return false;
  }

  for (unsigned int i = 0; i < value.length(); i++) {

    if (!isDigit(value[i])) {
      return false;
    }
  }

  return true;
}

// ============================================
// SERIAL COMMUNICATION
// ============================================

void resetTemperatureSafety();  // Prototipo para comandos Serial
void checkSerialCommands() {

  if (Serial.available() <= 0) {
    return;
  }

  String command = Serial.readStringUntil('\n');
  command.trim();

  // ALARM ON
  if (command == "ALARM:ON") {

    if (overheatDetected) { Serial.println("ERROR:THERMAL_LOCK"); return; }
    activateAlarm();
    return;
  }

  // ALARM OFF
  if (command == "ALARM:OFF") {

    deactivateAlarm();
    return;
  }

  // MOTOR ON
  if (command == "MOTOR:ON") {

    temperatureC = readTemperature();
    temperatureF = isnan(temperatureC) ? NAN : temperatureC * 1.8 + 32.0;
    checkTemperatureSafety();
    if (overheatDetected) {
      Serial.println("ERROR:THERMAL_LOCK");
      return;
    }
    motorRunning = true;

    updateMotor();

    if (currentMenu == 1) {
      showMotorMenu();
    }

    Serial.println("OK:MOTOR:ON");
    return;
  }

  // MOTOR OFF
  if (command == "MOTOR:OFF") {

    motorRunning = false;

    updateMotor();

    if (currentMenu == 1) {
      showMotorMenu();
    }

    Serial.println("OK:MOTOR:OFF");
    return;
  }

  // MOTOR SPEED
  if (command.startsWith("SPEED:")) {

    String value = command.substring(6);
    value.trim();

    if (!validNumber(value)) {

      Serial.println("ERROR:INVALID_SPEED");
      return;
    }

    int requestedSpeed = value.toInt();

    if (
      requestedSpeed < minSpeed ||
      requestedSpeed > maxSpeed
    ) {

      Serial.println("ERROR:SPEED_OUT_OF_RANGE");
      return;
    }

    motorSpeed = requestedSpeed;

    updateMotor();

    if (currentMenu == 1) {
      showMotorMenu();
    }

    Serial.print("OK:SPEED:");
    Serial.println(motorSpeed);

    return;
  }

  // RESET SECURITY ALERT
  if (command == "ALERT:RESET") {
    resetTemperatureSafety();
    return;
  }

  Serial.println("ERROR:UNKNOWN_COMMAND");
}

// ============================================
// SEND SENSOR DATA
// ============================================

void sendSensorData() {

  temperatureC = readTemperature();

  if (!isnan(temperatureC)) {

    temperatureF =
        temperatureC * 1.8 + 32;

  } else {

    temperatureF = NAN;
  }

  // Send Celsius to Raspberry Pi
  // Raspberry converts to Fahrenheit

  Serial.print("TEMP=");

  if (isnan(temperatureC)) {
    Serial.println("ERROR");
  } else {
    Serial.println(temperatureC, 1);
  }

  // Motor status
  Serial.print("MOTOR=");
  Serial.println(motorRunning ? "ON" : "OFF");

  // Motor speed
  Serial.print("SPEED=");
  Serial.println(motorRunning ? motorSpeed : 0);
}

// ============================================
// Overhetead Proteccion
// ============================================

void checkTemperatureSafety() {
  // sensor disconnected, motor is blocked for safety
  if (isnan(temperatureF) || temperatureF >= MAX_TEMPERATURE_F) {
    if (!overheatDetected) {
      overheatDetected = true;
      motorRunning = false;
      updateMotor();
      activateAlarm();
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print(isnan(temperatureF) ? "SENSOR ERROR" : "HIGH TEMPERATURE");
      lcd.setCursor(0, 1);
      if (isnan(temperatureF)) lcd.print("MOTOR STOPPED");
      else {
        lcd.print(temperatureF, 1);
        lcd.print(" F STOP");
      }
      Serial.println("ALERT:OVERHEAT");
    }
  }
  // The alarm stay active until reset buttom

}

// ============================================
// MANUAL THERMAL RESET (88 F OR LESS)
// ============================================

void resetTemperatureSafety() {
  temperatureC = readTemperature();
  temperatureF = isnan(temperatureC) ? NAN : temperatureC * 1.8 + 32.0;

  if (isnan(temperatureF)) {
    Serial.println("ERROR:SENSOR_FAILURE");
    return;
  }
  if (temperatureF > RESET_TEMPERATURE_F) {
    Serial.println("ERROR:TEMPERATURE_HIGH");
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("RESET DENIED");
    lcd.setCursor(0, 1);
    lcd.print("TEMP TOO HIGH");
    return;
  }

  motorRunning = false;
  overheatDetected = false;
  updateMotor();
  alarmActive = false;
  securityAlert = false;
  buzzerTimerActive = false;
  digitalWrite(buzzerPin, LOW);
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("SYSTEM RESET");
  lcd.setCursor(0, 1);
  lcd.print("MOTOR READY");
  Serial.println("OK:SYSTEM_RESET");
}

void keypadEvent(KeypadEvent key) {
  if (key == '#' && keypad.getState() == HOLD) {
    resetTemperatureSafety();
  }
}

// ============================================
// SETUP
// ============================================

void updateBuzzer() {
  if (buzzerTimerActive && millis() - buzzerStartTime >= BUZZER_DURATION) {
    digitalWrite(buzzerPin, LOW);
    buzzerTimerActive = false;
    Serial.println("BUZZER TIMEOUT");
  }
}

void setup() {

  Serial.begin(9600);
  Serial.setTimeout(100);

  pinMode(motorPin, OUTPUT);
  analogWrite(motorPin, 0);

  pinMode(buzzerPin, OUTPUT);
  digitalWrite(buzzerPin, LOW);

  lcd.begin(16, 2);
  keypad.setHoldTime(3000);
  keypad.addEventListener(keypadEvent);

  temperatureC = readTemperature();

  if (!isnan(temperatureC)) {
    temperatureF =
        temperatureC * 1.8 + 32;
  }

  checkTemperatureSafety();
  if (!overheatDetected) showMenu();

  Serial.println("OT SECURITY CONTROLLER V5 READY");
}

// ============================================
// MAIN LOOP
// ============================================

void loop() {

  updateBuzzer();


  // Update sensor data every 2 seconds
  if (millis() - lastSensorUpdate >= SENSOR_INTERVAL) {

    lastSensorUpdate = millis();

    sendSensorData();
    checkTemperatureSafety();
  }

  // Check Raspberry Pi commands after safety check
  checkSerialCommands();

  // Update LCD temperature every second
  if (
    currentMenu == 2 &&
    millis() - lastLCDUpdate >= LCD_INTERVAL
  ) {

    lastLCDUpdate = millis();

    showSensorMenu();
  }

  // Read keypad
  char key = keypad.getKey();

  if (!key) {
    return;
  }

  // Main menu
  if (key == '*') {
    showMenu();
    return;
  }

  // ========================================
  // MOTOR MENU
  // ========================================
  

  if (currentMenu == 1) {

    if (key == '1') {

      temperatureC = readTemperature();
      temperatureF = isnan(temperatureC) ? NAN : temperatureC * 1.8 + 32.0;
      checkTemperatureSafety();
      if (overheatDetected) {
        Serial.println("ERROR:THERMAL_LOCK");
      } else {
        motorRunning = true;
      }
      updateMotor();
    }

    else if (key == '2') {

      motorRunning = false;
      updateMotor();
    }

    else if (key == '3') {

      motorSpeed += 10;

      if (motorSpeed > maxSpeed) {
        motorSpeed = maxSpeed;
      }

      updateMotor();
    }

    else if (key == '4') {

      motorSpeed -= 10;

      if (motorSpeed < minSpeed) {
        motorSpeed = minSpeed;
      }

      updateMotor();
    }

    showMotorMenu();
    return;
  }

  // ========================================
  // ALARM MENU
  // ========================================

  if (currentMenu == 4) {

    if (key == '1') {
      if (!overheatDetected) activateAlarm();
    }

    else if (key == '2') {
      deactivateAlarm();
    }

    return;
  }

  // ========================================
  // MAIN MENU
  // ========================================

  if (key == 'A') {
    showMotorMenu();
  }

  else if (key == 'B') {
    showSensorMenu();
  }

  else if (key == 'C') {
    showSecurityMenu();
  }

  else if (key == 'D') {
    showAlarmMenu();
  }
}