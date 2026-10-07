#include <Servo.h>

Servo myServo;
Servo myESC;

const int ESC_STOP        = 1520;
const int ESC_FORWARD     = 1480;
const int ESC_FORWARD_SLOW = 1500;  // ラインを見失いそうな急カーブ用の減速値（STOPとFORWARDの中間）
const int ESC_REVERSE     = 1640;

const int STEER_CENTER = 120;   
const int STEER_LEFT   = 190;   
const int STEER_RIGHT  = 50;  

int currentESC = ESC_STOP;
bool waitingForCommand = false; // 💡 パスワード確認用のメモリ

void setup() {
  Serial.begin(9600);
  myServo.attach(9);
  myESC.attach(10, 1000, 2000);

  myESC.writeMicroseconds(ESC_STOP);
  myServo.write(STEER_CENTER);
  delay(3000);
}

void updateCar(int targetESC, int targetSteer) {
  if (targetESC == ESC_REVERSE && currentESC != ESC_REVERSE) {
    myESC.writeMicroseconds(ESC_REVERSE); 
    delay(200);
    myESC.writeMicroseconds(ESC_STOP);    
    delay(200);
  }
  
  currentESC = targetESC;
  myESC.writeMicroseconds(currentESC);
  myServo.write(targetSteer);
}

void loop() {
  while (Serial.available() > 0) {
    char command = Serial.read();

    // 💡 パスワード「:」が来たら、次の文字を命令として受け入れる準備をする
    if (command == ':') {
      waitingForCommand = true;
      continue; 
    }
    
    // 💡 パスワード確認済みの場合だけ、命令を実行！（それ以外は無視）
    if (waitingForCommand) {
      switch(command) {
        case 'Q': updateCar(ESC_FORWARD, STEER_LEFT); break;
        case 'W': updateCar(ESC_FORWARD, STEER_CENTER); break;
        case 'E': updateCar(ESC_FORWARD, STEER_RIGHT); break;

        case 'A': updateCar(ESC_STOP, STEER_LEFT); break;
        case 'X': updateCar(ESC_STOP, STEER_CENTER); break;
        case 'D': updateCar(ESC_STOP, STEER_RIGHT); break;

        case 'Z': updateCar(ESC_REVERSE, STEER_LEFT); break;
        case 'S': updateCar(ESC_REVERSE, STEER_CENTER); break;
        case 'C': updateCar(ESC_REVERSE, STEER_RIGHT); break;

        // ライントレースで「見失いそうな急カーブ」用の減速コマンド（自動運転専用）
        case 'Y': updateCar(ESC_FORWARD_SLOW, STEER_LEFT); break;
        case 'U': updateCar(ESC_FORWARD_SLOW, STEER_RIGHT); break;
      }
      // 実行が終わったら、またパスワード待ちに戻る
      waitingForCommand = false;
    }
  }
}