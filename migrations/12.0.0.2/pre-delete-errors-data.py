# -*- coding: utf-8 -*-

def migrate(cr, version):
    cr.execute("""
        delete from pe_datas where table_code='PE.CPE.ERROR'
    """)
