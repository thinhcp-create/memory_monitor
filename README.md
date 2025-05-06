App đọc flash hiển thị ra giao diện trực quan hỗ trợ cho những dòng chip hãng ko có app support đọc flash
app sẽ gửi lệnh xuống firmware theo cấu trúc "#w01 READ:begin,end.*" ví dụ "#w01 READ:286736,286752.*" (lưu ý dạng số nguyên uint32)
phía firmware khi nhận lệnh này sẽ đọc flash và gửi qua serial lệnh cấu trúc là "address_begin: data hex(độ dài tính theo begin và end)" ví dụ "46000: 24 00 5B 31 31 3A 34 31 3A 32 30 5F 30 30 30 30\n"
