# Runbook: High API Latency Response

## 🚨 Alert Information
- **Trigger**: Average API latency > 5 seconds
- **Alarm**: HighLatencyAlarm  
- **Severity**: P2 (Medium Priority)
- **Expected Response Time**: 30 minutes

## 🔍 Investigation Query
```sql
fields @timestamp, @message
| filter @message like /ApiLatency/
| parse @message '"ApiLatency": *' as latency
| stats avg(latency), max(latency), count() by bin(5m)
| sort @timestamp desc