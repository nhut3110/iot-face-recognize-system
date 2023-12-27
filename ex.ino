#include <LiquidCrystal_I2C.h>
#include <Wire.h>

LiquidCrystal_I2C lcd(0x3F, 16, 2);  // Địa chỉ I2C của màn hình LCD
char receivedData[32];  // Dùng để lưu trữ dữ liệu nhận từ Python
unsigned long lastDisplayTime = 0;
const unsigned long displayDuration = 5000;  // Thời gian hiển thị text trên LCD (ms)

void setup() {
    lcd.init();
    lcd.backlight();
    lcd.begin(16, 2);
    Serial.begin(9600);
}

void loop() {
    if (Serial.available() > 0) {
        int bytesRead = Serial.readBytesUntil('\n', receivedData, sizeof(receivedData) - 1);
        receivedData[bytesRead] = '\0';  // Thêm ký tự kết thúc chuỗi
        displayText(receivedData);
    }

    // Kiểm tra thời gian hiển thị và clear
    if (millis() - lastDisplayTime >= displayDuration) {
        lcd.clear();
    }
}

void displayText(const char *text) {
    lcd.clear();
    lcd.setCursor(0, 1);
    lcd.print(text);

    // Lưu thời gian hiển thị
    lastDisplayTime = millis();
}
