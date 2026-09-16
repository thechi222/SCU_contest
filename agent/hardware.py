import platform
import subprocess
import psutil
import pynvml as nv

def gpu(index=0):
    nv.nvmlInit()
    handle = nv.nvmlDeviceGetHandleByIndex(index)
    def decode(value):
        return value.decode() if isinstance(value,bytes) else value
    return {'gpu_uuid':decode(nv.nvmlDeviceGetUUID(handle)),
            'gpu_name':decode(nv.nvmlDeviceGetName(handle)),
            'memory_mb':int(nv.nvmlDeviceGetMemoryInfo(handle).total/1024**2),
            'driver':decode(nv.nvmlSystemGetDriverVersion()),'os':platform.platform()}

def telemetry(index=0):
    result = {}
    try:
        nv.nvmlInit(); handle = nv.nvmlDeviceGetHandleByIndex(index)
        for key, read in {
            'gpu_utilization':lambda: nv.nvmlDeviceGetUtilizationRates(handle).gpu,
            'memory_used_mb':lambda: nv.nvmlDeviceGetMemoryInfo(handle).used/1024**2,
            'memory_free_mb':lambda: nv.nvmlDeviceGetMemoryInfo(handle).free/1024**2,
            'temperature_c':lambda: nv.nvmlDeviceGetTemperature(handle,nv.NVML_TEMPERATURE_GPU),
            'power_w':lambda: nv.nvmlDeviceGetPowerUsage(handle)/1000,
        }.items():
            try: result[key]=read()
            except nv.NVMLError: result[key]=None
    except nv.NVMLError:
        pass
    battery=psutil.sensors_battery()
    result['on_ac']=battery.power_plugged if battery else None
    return result

def docker(args, timeout=20, check=True):
    return subprocess.run(['docker',*args],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout,check=check,
                          creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
