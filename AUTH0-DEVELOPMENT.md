# Maaher LMS — Auth0 development

Source aplikasi berada di [maaher-lms-starter](maaher-lms-starter).
Gunakan branch `feat/LMS-01-auth0-development` dan jalankan perintah aplikasi
dari subfolder tersebut.

- [Mengambil source dan konfigurasi Mac dengan aman](maaher-lms-starter/docs/MAC-SOURCE-SYNC.md)
- [Setup tenant/aplikasi Auth0](maaher-lms-starter/docs/AUTH0-SETUP.md)
- [Hasil validasi dan gate yang masih terbuka](maaher-lms-starter/docs/LMS-01-AUTH0-HANDOFF.md)

Source mencakup migration 0004, OIDC Authorization Code + PKCE, binding issuer/
subject dan checker lokal. Secret `.env` tidak disertakan. H1 produksi dan
review independen masih terbuka; tidak ada merge/deploy otomatis.
