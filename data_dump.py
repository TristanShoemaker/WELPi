import WELData

data = WELData.WELData()
data.data.reset_index(inplace=True)
data.data.dateandtime = data.data.dateandtime.astype(str)
print([typ for typ in data.data.dtypes])
data.data.to_excel(excel_writer="WEL_data_dump.xlsx")
