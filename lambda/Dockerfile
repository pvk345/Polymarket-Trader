FROM public.ecr.aws/lambda/python:3.11

RUN yum install -y gcc gcc-c++ python3-devel && yum clean all

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY models.py position_sizer.py settings.py polymarket.py trade_executor.py rule_evaluator.py handler.py ${LAMBDA_TASK_ROOT}/

CMD ["handler.handler"]
