from services.wikipedia import WikipediaService

#test wikipedia service
wiki_service = WikipediaService()
company_name = "Accenture"
wiki_result = wiki_service.get_company_info_wikipedia(company_name)
print(wiki_result)