FROM public.ecr.aws/lambda/python:3.12

COPY backend/requirements-runtime.txt ${LAMBDA_TASK_ROOT}/requirements.txt

RUN pip install \
    --no-cache-dir \
    --requirement ${LAMBDA_TASK_ROOT}/requirements.txt \
    --target ${LAMBDA_TASK_ROOT}

COPY backend ${LAMBDA_TASK_ROOT}/backend

CMD ["backend.app.lambda_handler.handler"]
