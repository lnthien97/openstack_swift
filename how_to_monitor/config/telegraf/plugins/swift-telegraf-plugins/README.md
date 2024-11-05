Repo dùng cho plugin swift áp dụng cho Telegraf agent. Để sử dụng đẩy nội dung repo vào thư mục plugins của telegraf /etc/telegraf/plugins/[plugin-name]

Kế tiếp copy file config khởi tạo inputs.exec từ các script liên quan service cần collect (tham khảo các config example kèm theo ví dụ swift-recon.conf.example) vào thư mục /etc/telegraf/telegraf.d/swift-recon.conf

## Telegraf exmaple config exc /etc/telegraf/telegraf.d/swift.conf
[[inputs.exec]]

commands = ["/etc/telegraf/plugins/swift/swift-disk","/etc/telegraf/plugins/swift/swift-load", "/etc/telegraf/plugins/swift/swift-replication" , "/etc/telegraf/plugins/swift/swift-async"]
json_name_key = "name"

tag_keys = ["role"]

timeout = "60s"

data_format = "json"
