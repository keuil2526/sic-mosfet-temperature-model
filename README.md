# SiC MOSFET Temperature-Dependent Modeling

SCT3080KL SiC MOSFET 한 개의 온도별 전기적 특성을 분석하는 Python 프로젝트입니다. 측정값을 data/temperature_measurements.csv에 입력하면 Vth, RDS(on), transfer/output curves, 수치 미분 기반 gm 및 온도 경험 모델을 계산합니다.

주의: 이 프로젝트는 단일 소자 분석용입니다. Planar/Trench 구조 비교나 소자 간 편차를 결론 내리지 않습니다. 실제 측정값을 임의로 생성하지 않습니다.

## 설치

Python 3.10 이상 권장.

    git clone https://github.com/keuil2526/sic-mosfet-temperature-model.git
    cd sic-mosfet-temperature-model
    python -m venv .venv
    source .venv/bin/activate
    python -m pip install -r requirements.txt

Windows에서는 가상환경 활성화 명령으로 .venv\Scripts\activate를 사용하세요.

## CSV 데이터 형식

data/temperature_measurements.csv의 헤더에 맞춰 실제 측정 행을 추가합니다. 제공된 CSV는 헤더만 있는 빈 템플릿입니다.

필수 열:
- temperature_C: 소자 온도(°C)
- curve_type: transfer, output, 또는 rds_on
- vgs_V: 게이트-소스 전압(V)
- vds_V: 드레인-소스 전압(V)
- id_A: 드레인 전류(A)

선택 열:
- rds_on_ohm: 직접 측정한 온저항(Ω)
- device_id: 소자 식별자
- notes: 측정 조건 메모

Transfer curve는 같은 온도에서 VGS를 바꾸며 측정한 ID 데이터입니다. Output curve는 VDS를 바꾸며 측정한 ID 데이터입니다. 온저항은 가능하면 직접 측정해 rds_on_ohm에 기록하세요. 직접 측정값이 없으면 스크립트가 설정된 VGS 부근의 유효한 VDS/ID 값을 추정치로 사용하지만, 이는 낮은 VDS의 ohmic 영역에서만 적절합니다.

단위는 V, A, Ω로 통일하세요. mA나 mΩ 값을 그대로 넣지 마세요. 온도는 섭씨로 입력합니다.

## 실행

    python analyze_sic_mosfet.py

분석 결과는 outputs/에 저장됩니다.
- summary.json: 설정, 적합 계수, 해석상 주의점
- vth_by_temperature.csv: 온도별 Vth 추정값
- rds_on_by_temperature.csv: 온도별 온저항 추정값
- transfer_curves.png, output_curves.png: 특성 곡선
- vth_temperature_fit.png: Vth의 온도별 선형 근사
- rds_on_temperature_fit.png: RDS(on)의 온도별 경험식 근사
- gm_by_temperature.csv 및 gm_by_temperature.png: 수치 미분 기반 gm

데이터가 부족하면 해당 분석은 건너뜁니다. 기본 추출 설정은 analyze_sic_mosfet.py 상단에서 변경할 수 있습니다. VTH_CURRENT_A는 Vth 추출 기준 전류이며, RDS_VGS_TARGET_V는 온저항 추정에 사용할 게이트 전압입니다.

## 모델 해석

Vth는 각 온도의 transfer curve에서 설정한 임계 전류에 해당하는 VGS를 선형 보간해 추정합니다. 따라서 보고서에 임계 전류 기준과 측정 조건을 명시해야 합니다.

데이터가 충분하면 Vth(T) = aT + b 선형 모델과 RDS(on)(T) = R0(TK/T0K)^m 경험적 거듭제곱 모델을 적합합니다. 이 모델들은 측정 범위의 데이터를 요약하기 위한 경험식이지, 모든 온도에서 성립하는 보편 법칙이 아닙니다. 측정 범위 밖으로 외삽하지 마세요.

gm = dID/dVGS는 transfer curve의 수치 미분으로 추정합니다. gm은 그 자체로 전자 이동도의 직접 측정값이 아닙니다. 이동도 추정에는 소자 구조·치수, 산화막 정전용량, 측정 영역 등 추가 정보가 필요합니다.

## 보고서에 남길 사항

소자명, 온도 측정 위치와 안정화 시간, 계측기, 측정 전압 범위·간격, Vth 기준 전류, RDS(on) 측정 방식, 반복 횟수, 불확도, 모델 적합 범위 및 잔차를 기록하세요. 원본 측정값을 보존하고, 이상치를 제거할 때는 기준을 명시하세요.
