# 新增 Calculator

1. 继承 `Calculator` 基类
2. 实现 5 个抽象方法
3. 注册到 `CalculatorRegistry`

from masgent.calculators.base import Calculator

class MyCalculator(Calculator):
    TYPE = "my_calc"

    async def prepare(self, structure, workflow_type, **kwargs):
        # 生成输入文件
        pass

    async def launch(self, work_dir):
        # 启动计算
        pass

    async def detect_status(self, work_dir, job=None):
        # 检测状态
        pass

    async def collect(self, work_dir, workflow_type):
        # 收集结果
        pass

    async def cancel(self, job):
        # 取消计算
        pass

    def get_init_params(self):
        return {...}


三、示例代码目录 `examples/`

每个示例文件应是独立可运行的脚本：

# examples/local_vasp.py
# examples/slurm_vasp.py
# examples/workflow_relax_static.py
# examples/recovery_demo.py