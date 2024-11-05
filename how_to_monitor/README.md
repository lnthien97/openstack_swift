What do we monitor ? 
- Logs
    + OS logs : 
        . /var/log/syslog : catch 'error message' and send to Engineer.
        . /var/log/auth.log : detect user's login events
    + swift services logs : /var/log/swift/*.log : Troubleshooting, Auditing (PUT/DELETE), catch error message and send alert to Engineers. 

- Metrics
    + 
- Processes 

- Hardware health : Disk, CPU, RAM , ...



What do we need ? 

- Metrics : Telegraf -> InfluxDB -> Grafana 
- Logs : Filebeat -> Kafka -> Logstash -> Elasticsearch -> Kibana 
- Processes : Monit
- Hardware health : CheckMK 

