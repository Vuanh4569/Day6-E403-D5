# Tool chuyển đổi PDF sang Text

Công cụ này giúp trích xuất nội dung văn bản từ một file PDF và lưu thành file `.txt`.

## Cài đặt thư viện yêu cầu

Trước khi chạy, bạn cần cài đặt thư viện `pypdf`:

```bash
pip install -r requirements.txt
```

## Cách sử dụng

Chạy script `convert.py` bằng Python:

```bash
python convert.py <đường-dẫn-file-pdf>
```

Ví dụ:
```bash
python convert.py tai_lieu.pdf
```
*Lưu ý: Mặc định file text đầu ra sẽ được lưu cùng thư mục với file PDF và có cùng tên nhưng đuôi `.txt`.*

Nếu bạn muốn tùy chỉnh tên file đầu ra, sử dụng tùy chọn `-o` hoặc `--output`:
```bash
python convert.py tai_lieu.pdf -o ket_qua.txt
```

## Cách chạy kiểm thử (Testing)

### 1. Chạy Unit Test tự động (Không cần file PDF thực tế)
Chúng tôi đã viết sẵn một bộ unit test sử dụng `unittest` của Python và cơ chế `mock` để kiểm tra logic của script (kiểm tra định dạng file, xử lý lỗi khi không tìm thấy file, và kiểm tra quá trình trích xuất văn bản từ các trang PDF).

Để chạy Unit Test, bạn thực hiện lệnh sau trong terminal:
```bash
python test_convert.py
```

### 2. Kiểm thử thủ công với file PDF thực tế
1. Chuẩn bị 1 file PDF bất kỳ (ví dụ: `test.pdf`).
2. Chạy lệnh:
   ```bash
   python convert.py test.pdf
   ```
3. Kiểm tra xem file `test.txt` có được tạo ra trong cùng thư mục không và kiểm tra nội dung bên trong có khớp với file PDF hay không.
