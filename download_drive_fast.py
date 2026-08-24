import os
import re
import time
import requests

# Danh sách toàn bộ các file trong thư mục Google Drive HĐ_Khách lẻ
DRIVE_FILES = [
    ("1xVwvyRRAzxgpAM5Yx4ooUBJe-Fl9uzoY", "01_Hop_Dong_RYLOV_ANDREI.docx"),
    ("1cA6k1JNuB9fPxQNN5Fn4piD_IIMxM-lk", "02_Hop_Dong_RIAZANOVA_ANASTASIIA.docx"),
    ("1fXE72o67tgzy99CMZxBTJenXWNo-cgTY", "03_Hop_Dong_NAZAROV_ANDREI.docx"),
    ("10FWWMpEZHmlZhpCHxVMpGq5VC7TKQKWQ", "04_Hop_Dong_Bolshakov_Andrei.docx"),
    ("1z_tsvKT004yG7IJKYCWoiRrQHpohgQ_w", "05_Hop_Dong_LEPERT_EVAN.docx"),
    ("13HfQpc4XDQhbQ57JCg_Etk4ZcXVr8WjT", "06_Hop_Dong_TOKAREVA__ANGELINA.docx"),
    ("1Td3-9nmaMgLWdAnsDWBRmrBHj3_5FP1M", "07_Hop_Dong_GALIMZHANOV_TIMUR.docx"),
    ("1SSvo2YoYc6W4Pkf6ZN9dS7b9a86kunWf", "08_Hop_Dong_DUMAN_TOLGAHAN.docx"),
    ("1IWiSKD1a7HdDBd3pRVH4uHYHrCISbuRL", "09_Hop_Dong_Tulupov_Daniil.docx"),
    ("1AZkFJe4p8sDzMfRnb69eusq87uQDkFor", "10_Hop_Dong_Gamanko_Iakov.docx"),
    ("1dQswxluduVGpUJg0IWrwBPqRZ0PzC-qr", "11_Hop_Dong_Kiriudchev_Ilia.docx"),
    ("1H66NFLwLyZR6wd3Wrc-Yss4qvtfPnd58", "12_Hop_Dong_KARIMZODA_ABDUNAIM.docx"),
    ("1j9m5o4-vY9MobjjZdzbSGeLKsIFSiriM", "13_Hop_Dong_SEMIONOV_IVAN.docx"),
    ("1Zx-tG8AOVk3is0XdVyu1bMrPazRgKG09", "14_Hop_Dong_SHABALA_YEVGEN_chuacochuky.docx"),
    ("10mLQMAy1G21iZ6N89eBORkD0pMs7W29r", "15_Hop_Dong_VOEVODIN_FEDOR.docx"),
    ("1FcW5R6hVlZcTSfe0tl0yDFLABe_nJfrs", "16_Hop_Dong_VOEVODIN_IVAN.docx"),
    ("1Gvd7OEB3bjZC1fWmDyOa7Ok8UXg0BDiG", "17_Hop_Dong_Chanida_Sitthisang.docx"),
    ("1SjPE00eQAFcGbigj_jmOcjtyMWPz4V2a", "18_Hop_Dong_Seiger_Molodtsov.docx"),
    ("1SCt1Ur6zJYMioxZVoszmEkO068uQz_YC", "19_Hop_Dong_GVOZDEV_SERGEY.docx"),
    ("1s7wfUF_PoFmW623uAPNYICv7vCb1NKU7", "20_Hop_Dong_PILETSKII_ALEKSANDR.docx"),
    ("1ZmnrIN3boAXcoPKfnSx-Pbd7JYRiX0RB", "21_Hop_Dong_BADIUk_KSENIIA.docx"),
    ("1BvvznulqFarg7n_LDxkfW5pRhAbziPvO", "22_Hop_Dong_GRACHEV_BOGDAN.docx"),
    ("1pGD6njApeloq7F5TGWlc0xfLz8qexos5", "23_Hop_Dong_SITNIKOVA_IANA.docx"),
    ("1zWflRcppLO8nXOjJdkG6n__QVVQSdr8S", "24_Hop_Dong_LEDNEV_ALEKSEI.docx"),
    ("12L9M8lcu5ygbzbu-_cp1zWJJnbGAenNz", "25_Hop_Dong_Filippnov_Aleksei.docx"),
    ("1HAWaABugIj9No-TpuHpNNzeICa-p4xZt", "26_Hop_Dong_KHILKO_NIKITA.docx"),
    ("1q_QHHMmpcDowOUjVLmiFGAm7tjIgzjr0", "27_Hop_Dong_FROLOV_ILIA.docx"),
    ("1nr-xkZpXV1S-cnfD7G0vK-Zl2cWeOO0g", "28_Hop_Dong_AGEIKIN_SAVELII.docx"),
    ("1fNbGsgc-JpITnABeWz43XdhBpkkvZCnY", "29_Hop_Dong_ORLOV_DANIIL.docx"),
    ("17fF571cTOmxKipPIO4buKNVPCYsUOXsr", "30_Hop_Dong_MUKHAMETDINOVA_IULIIA.docx"),
    ("1nZfJUAPV40fhLFY6xj1KnR5ZmGwlgbqu", "31_Hop_Dong_IVANENKO_SERGEI.docx"),
    ("1v5lDROAWG_vTa7ttUEkNh1xknqxGfSEC", "32_Hop_Dong_KHABAROVA_VIKTORIIA.docx"),
    ("114CG7ta1oIsWavwMOac1QlpM4wQ98MCl", "33_Hop_Dong_Lacey_Jason_William.docx"),
    ("1Wa73VasHwDGE97PeCRhf9r6QK2kwGA6G", "34_Hop_Dong_KHOMYAKOVA_DARIA.docx"),
    ("1Qj8YOiXXPMdr9IqdUXsgpweE0jBODRNZ", "35_Hop_Dong_Chernushenko_Vladimir.docx"),
    ("1_O667Hx_b8HeltAsKR0TFZb-_f7aBQIo", "36_Hop_Dong_RUSSKIN_DMITRII.docx"),
    ("1W3Fpx54HETOvvBJ62OLGRBkx9OSBaXRU", "37_Hop_Dong_RUSSKINA_ANASTASIIA.docx"),
    ("1yRQP7Xt4QOFJqFiVWwsrafcrb79nXphH", "38_Hop_Dong_GOROBETC_KIRILL.docx"),
    ("1EOrMz3nI6Cb2aVXOg8pDknvIWrEenbJz", "39_Hop_Dong_KLEMENTEV_MIKHAIL_chukybikhuat.docx"),
    ("1eGBSyI2Qv4FzdOpq4h7VyYFQO-cDaoiO", "40_Hop_Dong_ORLOVA_TATYANA.docx"),
    ("1arIWv9nLDJGx2o0Ft6PbANmTNyMdEP8O", "41_Hop_Dong_MONASTYRYOV_ROMAN.docx"),
    ("1USHl7onYr-enKMGSPzp3dmYWh3jnBg6H", "42_Hop_Dong_SAPOZHNIKOV_SEMEN.docx"),
    ("1o5XMzZTaxNaF9G29j3EpuH9aQENgJvlI", "43_Hop_Dong_Jung_Young_Mi_kocochuky.docx"),
    ("1Bx_3JZOZ_BGL1p4Vik-5dW1pFPcga-Et", "44_Hop_Dong_PASKAL_VALENTIN_kocochuky.docx"),
    ("1WVN57KEV2O32M2d5ykx0PXD8myQuHmvn", "45_Hop_Dong_KNIAZKOV_STANISLAV.docx"),
    ("1eBfhPwaZwUPp7JnN2AAK2krOuWx55vUh", "46_Hop_Dong_KOSTYGINA_IRINA.docx"),
    ("1lILBp0rcxtZa6APyapKwDo_Ou5PImcww", "47_Hop_Dong_AL-SHAMIRI_LEILA.docx"),
    ("13asHmVSWbaPplNFOrcOoWKzkHkF7MCJD", "48_Hop_Dong_Kazantseva_Anastasiia.docx"),
    ("17oGUamPSh7RoFiL6ESiwQwF6Vsmb5Ktd", "49_Hop_Dong_Kazantseva_Arina_kocochuky.docx"),
    ("1-QnO2pmFhLdoI1ivIYRnWvf4THvskZGp", "50_Hop_Dong_Burim_Denis.docx"),
    ("1GgVVugQ6MwWHNotEdgHWr3DNs-_i-Q19", "51_Hop_Dong_IAKUPOV_EMIL.docx"),
    ("14EHbYivsbQMuKb8He1n6phNhZoOu28-O", "52_Hop_Dong_ABUBIKIROV_ARSLAN_RASHIDOVICH.docx"),
    ("1q1xWwtNcW799-8qOpKmpM5CiOAvO8v3T", "53_Hop_Dong_BAKUSEV_TIMUR.docx"),
    ("102kT_LMk4_qLQPKknYKmRhoxxlkeQbpI", "54_Hop_Dong_TERESHCHENKO_OLEKSII.docx"),
    ("1BceXTzB9V6lS5DhuTxjE5dYFKP8IDtr5", "55_Hop_Dong_Choi_Changmin.docx"),
    ("1DKEP1OrfPm_xtK-U9un6w3ppWAZtY-Gb", "56_Hop_Dong_GORBACHEV_ROMAN.docx"),
    ("1Uvp-FZql0bAssjzq2xiUAoVKKy0VQL2T", "57_Hop_Dong_PAPOUSKI_YURY.docx"),
    ("15q2VmGlKkkDHqyp9RccNZPHV5P-R-wZT", "58_Hop_Dong_Wurger_Peter.docx"),
    ("1BU3HK-NQlYzQcvCA3h1ZgSz1CxN0T3H8", "59_Hop_Dong_KONDRATEVA_EKATERINA__cancel_kocochuky.docx"),
    ("1QODOqyI_Ik-6O1z_LuryfEENxYnGKJuJ", "60_Hop_Dong_Quinn_Michael.docx"),
    ("1vPGpqaN6hUJgD8ABL7m1cXppD5dhTyfB", "61_Hop_Dong_OZNOBIKKIN_IAROSLAV.docx"),
    ("1_TYTuVA_ydN3LPerTjfu4I5Jtv8Bdi4p", "62_Hop_Dong_OZNOBIKHINA_ALEKSANDRA.docx"),
    ("1KQDnQal99VVcR2QqqajS77X6jO_GIUI_", "63_Hop_Dong_OZNOBIKHINA_MARINA_kocochuky.docx"),
    ("1pgG35DYuRjFjStZuDS7SA6-nljNGDkjA", "64_Hop_Dong_OZNOBIKHIN_DANIIL_kocochuky.docx"),
    ("1yZ1sFZOIMq1ENrZBw-BbxutGKN5AOVS-", "65_Hop_Dong_KANG_EUN_HYE_kocochuky.docx"),
    ("1a0GjjHWwr-oFv6UOHlA1co8Z4680v3oP", "66_Hop_Dong_CHYNYBAEV_TIMIRLAN.docx"),
    ("1D9wcXWo7PiPemjutuycA1dpWas7WcLE8", "67_Hop_Dong_PYAE_HTOO_KYAW.docx"),
    ("12J5IPiF7wPk_0HEJYqTJYlsX7ZqyEOyA", "68_Hop_Dong_Zemskov_Daniil.docx"),
    ("17gBKTNiJT_O6uurFqCXqgUt2H3aXnnLZ", "69_Hop_Dong_DOSAEVA_FATIMA.docx"),
    ("1CUkHzLAyp7q7HTTikjmh_toy2f_kQ7vd", "70_Hop_Dong_Slancik_Ladislav.docx"),
    ("1aB91KF_fZApltynom4DDZy8Azo7bzT70", "71_Hop_Dong_LINDBLAD_MADISON_J_kocochuky.docx"),
    ("1bzccOjjgVAFk5IOHTzuC-Nnol_YCt-QH", "72_Hop_Dong_LINDBLAD_COLTON_DAVID_kocochuky.docx"),
    ("1Vuv4a2jV61WI-TIkOr9qpRZ7KevGEmnQ", "73_Hop_Dong_KANG_EUN_HAE_kocochuky.docx"),
    ("1TtcL3tkBuumsmQveaBsUNS-XC7ksLIP4", "74_Hop_Dong_HWANG_SEON_DAE_kocochuky.docx"),
    ("1NS4b7IBcgIK7bEtVDs47fkPdcSePv7JL", "75_Hop_Dong_yeum_gwangseop.docx"),
    ("15qqKA80mFOvxE6DZWdoEFCC3U4eo04VZ", "76_Hop_Dong_CHASOVITIN_VITALII.docx"),
    ("1N-5RHurVTD-o3z31cCBEHOaf-_drIQwX", "77_Hop_Dong_LIM_BYEONGJOON_kocochuky.docx"),
    ("1rYtbnVKFbCdmul4jVlcdj6hY7FfktYwK", "78_Hop_Dong_FERREIRA_PEREIRA_ANDRE_kocochuky.docx"),
    ("1rlrGMmM8UWdeQoWkkD3wJ0SHE9c_cBZ2", "79_Hop_Dong_HACIEFEND_O_LU_Y___T.docx"),
    ("1a9qxLMcqQqM8idSdGeKTi9fME-il6YqZ", "80_Hop_Dong_RUD_SERHII.docx"),
    ("1RhrLAcwNbqoaFny8KX13XRsMdgri-hiK", "81_Hop_Dong_OZNOBIKKIN_IAROSLAV.docx"),
    ("1gz53GohfBuNf2Mhi4omCMz0WicRrxBgR", "82_Hop_Dong_OZNOBIKHINA_ALEKSANDRA.docx"),
    ("1Az3MSuWBHtSDofLO1NLKzVkzzcGPZB8-", "83_Hop_Dong_OZNOBIKHINA_MARINA.docx"),
    ("13UuAabH6tA_jZLuTMG_XdKYzuhL_gJiZ", "84_Hop_Dong_OZNOBIKHIN_DANIIL.docx"),
    ("1B3mgLb_H8aLZ8z0omB3Jx0Ozc9QDfToi", "85_Hop_Dong_Askarbekov_Ulangazy.docx"),
    ("1d2FtRw0r8wKUNzcAZvH54QB2V_VmsRt-", "86_Hop_Dong_ASIANOV_BULAT.docx")
]

# Chữ ký (nếu còn thiếu)
SIGNATURE_FILES = [
    ("1gK98I_bbixu7Fe-UREMQHEkAb3_Xtch2", "01.jpg"),
    ("1WQoiRt1PYmza7BZ9iMHAcvZcqjwfso3a", "02.jpg"),
    ("17IyQ7HAKNov6ksq1hNjZDloepB2Vw68N", "03.jpg"),
    ("1ZdpE1x_5GuzjTnppUF9ZOSGTHmwQ7jOz", "04.jpg"),
    ("1mXDyFxhZahKasotN-5wJRgsRTeRl_TOk", "05.jpg"),
    ("1S66W0GNDxvvjKIeciWlZwrZHYeGa5u2q", "06.jpg"),
    ("18rmd3z1OWds_x4ASVGo3w_V1V-nvROaB", "07.jpg"),
    ("1JbBOqFq7mGcmQkCbZLuEMztwR7_bVGAb", "08.jpg"),
    ("1jgpQjHa637t4-b-0JumE_TyjbIIcu6ec", "09.jpg"),
    ("1hxR7ktidM9F4T15JZNcDihuO-ps2EwBO", "10.jpg"),
    ("1isUuZ09Xl6-h_g5ZG2YR71JPtWso4RYR", "11.jpg"),
    ("1MJ7qomWG9nGeQQ2Ay9HOBxXRA8bLl2Q_", "12.jpg"),
    ("1a6mhvwCcH0rvJgh3gdKQfBp00e4MdndO", "13.jpg"),
    ("1usSDJdAplTti2wGGfyVzhnZoBA6obcI3", "14.jpg"),
    ("1-EZNk39cQWKP0TCusby1TJY8sQ7CotMv", "16.jpg"),
    ("12j_zYlW9lWyORocTLslK4abTKIrSJ0dd", "17.jpg"),
    ("1bULhs7z4KR0ZvIpC9UvorwOek-3-zaTO", "18.jpg"),
    ("17uh0GokPgwaolDqrFITciyhiqNM6hs3P", "19.jpg"),
    ("1ZFWAEV-p_PPiQq-WIL42PMbydOo4071q", "20.jpg"),
    ("1i8Aj0IJZ-az7BvVnBLTyw3Gti4qm_Mdq", "21.jpg"),
    ("1u86PgdCtu_H9POM3NCfMzNFIyaND44sC", "22.jpg"),
    ("1cjKTDGwfGA77LUpw099QGyqq7xQGNQl6", "23.jpg"),
    ("1BgLHcTSrfX99SlgcxdXoSiwZ3jB2Gxcu", "24.jpg"),
    ("1a2hO8N70uGDvMb--auhTFFUASjZTznch", "25.jpg"),
    ("1RJFcfMM653LCfJQnWga_eAg8tAopZj_P", "26.jpg"),
    ("1bZYPPUqbaGB_nB0TX2nBVhJwB6bYmPEO", "27.jpg"),
    ("1S74fzqGhqydGni9FNtliMpZpF3pVPtJ4", "28.jpg"),
    ("14465rrkqlcMj5RxZO3GqHvgbnhzpyakC", "29.jpg"),
    ("1A4x6wEzi_ajMEczBhMiXxs5MktZ_Y2Ht", "30.jpg"),
    ("1uWL5whR8F2bk6vXf595X7rREU4xm4FGN", "31.jpg"),
    ("1032QZYcFCRry_EtQhTvf7HEcwtPlBWBC", "32.jpg"),
    ("1gYrV1aIo-oZ-lEbsKUe8ovmZ7VsBlKg4", "33.jpg"),
    ("1Oaxi4B-m2pGvdpybZDuT3PSy2aDyZwjS", "34.jpg"),
    ("1HVehHOdAg2gTj-CM80eU0akL7TjxO69Y", "35.jpg"),
    ("1AXRzmuPWgZ1wCcQbjiyA8EcMYxldSQ47", "36.jpg"),
    ("1zmxc_sq6oeHzBvM70X49kfxC9Eh1a6FQ", "37.jpg"),
    ("1f7HBd0iGuMaF1OAEqZjMA4cjskVIXqg1", "38.jpg"),
    ("1SQfyFfkqnA8r39OJmWlyorltkSaZSKuP", "40.jpg"),
    ("1fE9FxEjIYpFbQrIF2kjmr0sR3W2DkHgc", "41.jpg"),
    ("1ZEC6zgV8jZsbCBP4A1wqQN4MMCGHolKM", "42.jpg"),
    ("1y_YFLAj0_j7krPCjGvaCKcubzFGzE-_F", "45.jpg"),
    ("1kVpPr4CbPvPyZrDYqqXS5mNf9W7JaYGK", "46.jpg"),
    ("1Xl0QQWPIPdj1p6nBZ5CIpgK0RBQli9-M", "47.jpg"),
    ("1BUOIWHHBIdWeBGj30lLCETJ4PFTu9T9G", "48.jpg"),
    ("1Mr54_ziXSgPh3_zYvh1KMEqsHc9bHTCm", "50.jpg"),
    ("1LZD9eEirP2PFzWehddBE2WUwhLrDE3wo", "51.jpg"),
    ("1jpgsCG4RXJ4qtGa4wkwWcJdOvOTthEqW", "52.jpg"),
    ("1fqHUJOXPnSrw2m-4hwkKt3MC_S_9Qm2N", "53.jpg"),
    ("1b29WHwU8fijn3rU0tgwJm0BcpA0jw5aZ", "54.jpg"),
    ("10ittGsg6Oc4RMP5tQlzQmg1IdddVKz_Z", "55.jpg"),
    ("1Sq_-yA9MwUOjTFEuDanH5_TuWM4Wnjnl", "56.jpg"),
    ("1-7bI4R52Fvun-bZj7DlwbHN20ob9LKAx", "57.jpg"),
    ("1jpM6yMsJ5AxGdn9qHPdVSokpLEKrfTvE", "58.jpg"),
    ("1UeFs87CLhxyOSJgjdUBN_pED5805IBjb", "60.jpg"),
    ("1XMHi1bONpZ-dwo7zKjtcmQFYgi8m4t0v", "61.jpg"),
    ("1zpOGSCDbkjK-FRWiNfWxVneUINYTeI49", "62.jpg"),
    ("1w9YgCBt0k0cZLxtsMcftukr_0j483Mwf", "66.jpg"),
    ("1dVBLVUGavx_CD3VltWNhSjpKrumm00XI", "67.jpg"),
    ("1Odb--UuV35CaFu3jwMhO_NMpmOi7kNX-", "68.jpg"),
    ("1G4iIajJsJjl2X94l0NKHT4GTICJYxTFh", "69.jpg"),
    ("1VPXVCCSRBr1pnXp-dzv9BmjYXFh7aJkA", "70.jpg"),
    ("101u1pFD0h0GanM5CkEBnbtSEI6p3tj6J", "75.jpg"),
    ("15T8mpQm35T1fZMLyoUigYpbjSD9rFBDr", "76.jpg"),
    ("1GFHihdpm95EwF_ayldCy6dhiVs-JCRHa", "79.jpg"),
    ("1y4MMamGGzExV_4M1CirYLecJfwYlOY2q", "80.jpg"),
    ("1PlimxWsyaifh3fSDi_yGzUWvT1TXQegK", "81.jpg"),
    ("1Z_AuK12hJpi8V-hthnb8S7ixHx03-wMR", "82.jpg"),
    ("1dzDVtuwSXIbHygIFaM7ACJR755PMK1gE", "85.jpg"),
    ("11HjiJ9UKPMlrKqON7sqEBPOIMiKXYDk3", "86.jpg")
]


def download_all_files():
    session = requests.Session()
    
    # 1. Tải thư mục HĐ_Khách lẻ (.docx)
    out_docx_dir = "HD_Khach_le/HĐ_Khách lẻ"
    os.makedirs(out_docx_dir, exist_ok=True)
    
    print(f"📥 Đang tải {len(DRIVE_FILES)} file hợp đồng Word (.docx)...")
    success_docx = 0
    for file_id, filename in DRIVE_FILES:
        target_path = os.path.join(out_docx_dir, filename)
        if os.path.exists(target_path) and os.path.getsize(target_path) > 1000:
            success_docx += 1
            continue
            
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        try:
            r = session.get(url, timeout=20, allow_redirects=True)
            if r.status_code == 200 and len(r.content) > 500:
                with open(target_path, "wb") as f:
                    f.write(r.content)
                success_docx += 1
                print(f"  ✅ Tải xong ({success_docx}/{len(DRIVE_FILES)}): {filename}")
            else:
                print(f"  ⚠️ Thử lại: {filename} (HTTP {r.status_code})")
        except Exception as e:
            print(f"  ⚠️ Lỗi: {filename}: {e}")
        time.sleep(0.1)

    # 2. Tải thư mục chữ ký khách hàng
    out_sig_dir = "HD_Khach_le/chữ ký khách hàng"
    os.makedirs(out_sig_dir, exist_ok=True)
    
    print(f"\n📥 Đang kiểm tra {len(SIGNATURE_FILES)} file ảnh chữ ký...")
    success_sig = 0
    for file_id, filename in SIGNATURE_FILES:
        target_path = os.path.join(out_sig_dir, filename)
        if os.path.exists(target_path) and os.path.getsize(target_path) > 500:
            success_sig += 1
            continue
            
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        try:
            r = session.get(url, timeout=20, allow_redirects=True)
            if r.status_code == 200 and len(r.content) > 500:
                with open(target_path, "wb") as f:
                    f.write(r.content)
                success_sig += 1
                print(f"  ✅ Tải chữ ký: {filename}")
        except Exception as e:
            print(f"  ⚠️ Lỗi tải chữ ký {filename}: {e}")
        time.sleep(0.1)

    print(f"\n🎉 HOÀN TẤT! Đã tải thành công:")
    print(f"  - Hợp đồng Word: {success_docx}/{len(DRIVE_FILES)} tệp tại '{out_docx_dir}'")
    print(f"  - Chữ ký khách hàng: {len(os.listdir(out_sig_dir))} tệp tại '{out_sig_dir}'")


if __name__ == "__main__":
    download_all_files()
