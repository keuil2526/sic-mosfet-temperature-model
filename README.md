# SCT3080KL 온도별 전기적 특성 분석

SCT3080KL SiC MOSFET 20개 소자의 25°C, 100°C, 150°C 측정값을 분석하는 Python 프로젝트입니다. 입력 데이터는 소자별 주요 전기적 파라미터 요약값이며, 원시 Transfer/Output Curve 데이터가 아닙니다.

## 설치 및 실행

```bash
git clone https://github.com/keuil2526/sic-mosfet-temperature-model.git
cd sic-mosfet-temperature-model
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python analyze_sic_mosfet.py
```

Windows에서는 `.venv\\Scripts\\activate`로 가상환경을 활성화합니다.

## 입력 데이터

- `data/sct3080kl_measurements.csv`: 제공받은 엑셀의 `소자별` 시트를 분석용 long-format CSV로 변환한 데이터
- 한 행은 한 소자의 한 온도에서의 측정값을 의미합니다.
- 단위는 열 이름에 표시되어 있습니다.
- 20번 소자의 100°C 행은 원본에서 측정값이 없으므로 빈칸으로 유지했습니다. 결측값은 보간하거나 임의로 채우지 않습니다.

분석 항목:
- `IDSS`: 드레인 누설 전류 (µA)
- `IGSS+`, `IGSS−`: 양·음 게이트 누설 전류 (nA)
- `VGS(th)`: 문턱 전압 (V)
- `RDS(on)`: 온저항 (mΩ)
- `gfs`: 순방향 전달 컨덕턴스 (S)

항복 전압 열의 `>1200`은 실제 항복전압이 1200 V라는 뜻이 아니라 1200 V보다 크다는 검열(censored) 측정값입니다. 따라서 정확한 평균 항복전압 계산에는 사용하지 않습니다.

## 출력

실행 후 `outputs/`에 다음 파일이 생성됩니다.

- `summary.json`: 분석 요약, 온도별 표본 수, 모델 계수 및 제한 사항
- `*_summary.csv`: 온도별 평균, 표준편차, 중앙값, 최소·최대
- `*_individual.png`: 소자별 온도 변화 그래프
- `*_mean_sd.png`: 온도별 평균 ± 표준편차 그래프
- `*_paired_change.csv`: 동일 소자 쌍을 기준으로 한 온도 구간별 변화량 및 변화율

## 해석상 주의사항

1. 이 파일에는 요약 측정값만 있으므로 Transfer Curve와 Output Curve를 재구성하거나 원시 곡선에서 Vth/gm을 다시 추출하지 않습니다.
2. VGS(th), RDS(on), gfs는 엑셀에 기록된 측정값과 해당 측정 조건을 그대로 사용합니다.
3. 20번 소자의 100°C 값은 결측으로 처리합니다. 해당 온도의 평균은 유효 측정값만으로 계산됩니다.
4. 온도별 선형 적합은 측정한 25–150°C 범위 안에서만 기술적으로 해석합니다. 측정 범위 밖으로 외삽하지 않습니다.
5. 소자별 궤적과 paired change는 동일 소자의 온도 변화 및 소자 간 편차를 함께 살펴보기 위한 것입니다. 소자 구조(Planar/Trench) 비교를 의미하지 않습니다.
6. 원본 엑셀의 측정 조건과 불확도 설명은 연구 보고서에 함께 기록해야 합니다.
