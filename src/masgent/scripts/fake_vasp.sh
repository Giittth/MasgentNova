#!/bin/bash
# Fake VASP - 用于测试 VASP 执行链路
# 用法: ./fake_vasp.sh [SLEEP_TIME] [EXIT_CODE]
#   SLEEP_TIME: 模拟运行秒数（默认 3）
#   EXIT_CODE: 退出码（默认 0，非 0 模拟失败）

SLEEP_TIME=${1:-3}
EXIT_CODE=${2:-0}

echo "Fake VASP started at $(date)"
echo "Sleep time: ${SLEEP_TIME}s, Exit code: ${EXIT_CODE}"

sleep $SLEEP_TIME

# 如果 EXIT_CODE != 0，模拟失败
if [ "$EXIT_CODE" != "0" ]; then
    echo "Fake VASP failed with exit code $EXIT_CODE"
    exit $EXIT_CODE
fi

# 生成 OUTCAR
cat > OUTCAR << 'EOF'
 vasp.5.4.4 18Apr19 (build Apr 19 2019 10:46:51) complex
 running on 1 nodes
 free energy   TOTEN  =    -10.53200000 eV
 Voluntary context switches: 123
EOF

# 生成 vasprun.xml
cat > vasprun.xml << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<modeling>
    <calculation>
        <energy>
            <i name="e_fr_energy"> -10.53200000</i>
            <i name="e_wo_entrp"> -10.53200000</i>
        </energy>
    </calculation>
</modeling>
EOF

# 生成 CONTCAR（从 POSCAR 复制）
if [ -f POSCAR ]; then
    cp POSCAR CONTCAR
    echo "CONTCAR generated from POSCAR"
fi

# 关键：写入 COMPLETED 标记，使 detect_status 能识别完成
touch COMPLETED

echo "Fake VASP completed at $(date)"
exit 0