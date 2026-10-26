from flask_wtf import FlaskForm
from flask_wtf.file import MultipleFileField
from wtforms import HiddenField, EmailField, PasswordField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, Regexp, ValidationError


def clean_text(value):
    return value.strip() if value else value


def required():
    return DataRequired(message="Bagian ini wajib diisi.")


class IndonesianSelectField(SelectField):
    def pre_validate(self, form):
        try:
            super().pre_validate(form)
        except ValidationError as error:
            raise ValidationError("Pilihan tidak valid. Pilih salah satu data yang tersedia.") from error

    def process_formdata(self, valuelist):
        try:
            super().process_formdata(valuelist)
        except ValueError as error:
            raise ValueError("Pilihan tidak valid.") from error


class LoginForm(FlaskForm):
    email = EmailField("Alamat email", filters=[clean_text], validators=[required(), Email(message="Alamat email tidak valid."), Length(max=190, message="Email maksimal 190 karakter.")])
    password = PasswordField("Kata sandi", validators=[required(), Length(max=128, message="Kata sandi maksimal 128 karakter.")])


class RegisterForm(FlaskForm):
    nama = StringField("Nama lengkap", filters=[clean_text], validators=[required(), Length(min=2, max=100, message="Nama harus terdiri dari 2-100 karakter.")])
    email = EmailField("Alamat email", filters=[clean_text], validators=[required(), Email(message="Alamat email tidak valid."), Length(max=190, message="Email maksimal 190 karakter.")])
    no_hp = StringField("Nomor HP (opsional)", filters=[clean_text], validators=[Optional(), Length(max=25, message="Nomor HP maksimal 25 karakter."), Regexp(r"^[+0-9 ()-]+$", message="Nomor HP tidak valid.")])
    rw_id = IndonesianSelectField("Rukun Warga (RW)", coerce=int, validators=[required()])
    rt_id = IndonesianSelectField("Rukun Tetangga (RT)", coerce=int, validators=[required()])
    password = PasswordField("Kata sandi", validators=[required(), Length(min=10, max=128, message="Gunakan 10-128 karakter.")])
    confirm = PasswordField("Ulangi kata sandi", validators=[required(), EqualTo("password", message="Kata sandi tidak sama.")])


class ComplaintForm(FlaskForm):
    submission_token = HiddenField("Token pengiriman", validators=[required()])
    judul = StringField("Judul pengaduan", filters=[clean_text], validators=[required(), Length(min=8, max=160, message="Judul harus terdiri dari 8-160 karakter.")])
    kategori_id = IndonesianSelectField("Kategori pengaduan", coerce=int, validators=[required()])
    lokasi_teks = StringField("Lokasi kejadian", filters=[clean_text], validators=[required(), Length(min=5, max=255, message="Lokasi harus terdiri dari 5-255 karakter.")])
    deskripsi = TextAreaField("Ceritakan permasalahannya", filters=[clean_text], validators=[required(), Length(min=20, max=5000, message="Deskripsi harus terdiri dari 20-5000 karakter.")])
    foto = MultipleFileField("Foto pendukung (opsional)")


class PasswordForm(FlaskForm):
    current_password = PasswordField("Kata sandi saat ini", validators=[required(), Length(max=128, message="Kata sandi maksimal 128 karakter.")])
    password = PasswordField("Kata sandi baru", validators=[required(), Length(min=10, max=128, message="Gunakan 10-128 karakter.")])
    confirm = PasswordField("Ulangi kata sandi baru", validators=[required(), EqualTo("password", message="Kata sandi tidak sama.")])
