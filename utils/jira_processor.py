from datetime import datetime
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JiraProcessor:
    def __init__(self):
        # Mapeamento dos custom fields para divergências
        self.divergencia_fields = [
            'key', 'created', 'status', 
            'customfield_10466',  # Tipo de CD
            'customfield_10300',  # Tipo de Divergencia
            'customfield_10433',  # Data de Recebimento
            'customfield_10169',  # Loja
            # Campos de quantidade e materiais (grupos de produtos)
            'customfield_11070', 'customfield_11071', 'customfield_11072', 'customfield_11073',
            'customfield_11074', 'customfield_11075', 'customfield_11076', 'customfield_11077',
            'customfield_11078', 'customfield_11079', 'customfield_11080', 'customfield_11081',
            'customfield_11082', 'customfield_11083', 'customfield_11084', 'customfield_11085',
            'customfield_11086', 'customfield_11087', 'customfield_11088', 'customfield_11089',
            'customfield_11090', 'customfield_11091', 'customfield_11092', 'customfield_11093',
            'customfield_11094',
            # Campos adicionais
            'customfield_10314', 'customfield_10315', 'customfield_10417', 'customfield_10423',
            'customfield_10318', 'customfield_10319', 'customfield_10418', 'customfield_10424',
            'customfield_10340', 'customfield_10346', 'customfield_10420', 'customfield_10425',
            'customfield_10342', 'customfield_10347', 'customfield_10421', 'customfield_10426',
            'customfield_10344', 'customfield_10348', 'customfield_10422', 'customfield_10427'
        ]

    def process_issues(self, issues, extract_type):
        logger.info(f"Processando {len(issues)} issues para tipo: {extract_type}")
        
        if extract_type == 'divergencias':
            return self.process_divergencias_complete(issues)
        elif extract_type == 'avarias':
            return self.process_avarias(issues)
        elif extract_type == 'qualidade':
            return self.process_qualidade(issues)
        elif extract_type == 'devolucoes':
            return self.process_devolucoes(issues)
        else:
            logger.error(f"Tipo de extração não suportado: {extract_type}")
            return []
    
    def process_divergencias_complete(self, issues):
        """Processamento completo de divergências com debug"""
        logger.info("Iniciando processamento de divergências")
        processed = []
        issues_with_products = 0
        
        for i, issue in enumerate(issues):
            logger.info(f"Processando issue {i+1}/{len(issues)}: {issue.get('key', 'N/A')}")
            
            fields = issue.get('fields', {})
            
            # Debug: mostrar alguns campos
            logger.debug(f"Status: {fields.get('status', {}).get('name', 'N/A')}")
            logger.debug(f"Loja: {self.get_custom_field_value(fields, 'customfield_10169')}")
            
            # Extrair dados básicos
            base_record = {
                'LOG': issue.get('key', ''),
                'Status': fields.get('status', {}).get('name', ''),
                'Data de Criação': self.format_date(fields.get('created')),
                'Tipo de CD': self.get_custom_field_value(fields, 'customfield_10466'),
                'Tipo de Divergencia': self.get_custom_field_value(fields, 'customfield_10300'),
                'Data de Recebimento': self.format_date(self.get_custom_field_value(fields, 'customfield_10433')),
                'Loja': self.get_custom_field_value(fields, 'customfield_10169'),
            }
            
            # Processar grupos de produtos
            products_found = False
            product_groups = [
                # Grupo 1: 11070-11075
                {
                    'produto': 'customfield_11070',
                    'categoria': 'customfield_11071', 
                    'qtd_cobrada': 'customfield_11072',
                    'qtd_recebida': 'customfield_11073',
                    'kg_cobrada': 'customfield_11074',
                    'kg_recebida': 'customfield_11075'
                },
                # Grupo 2: 11076-11081
                {
                    'produto': 'customfield_11076',
                    'categoria': 'customfield_11077',
                    'qtd_cobrada': 'customfield_11078', 
                    'qtd_recebida': 'customfield_11079',
                    'kg_cobrada': 'customfield_11080',
                    'kg_recebida': 'customfield_11081'
                },
                # Grupo 3: 11082-11087
                {
                    'produto': 'customfield_11082',
                    'categoria': 'customfield_11083',
                    'qtd_cobrada': 'customfield_11084',
                    'qtd_recebida': 'customfield_11085', 
                    'kg_cobrada': 'customfield_11086',
                    'kg_recebida': 'customfield_11087'
                },
                # Grupo 4: 11088-11093
                {
                    'produto': 'customfield_11088',
                    'categoria': 'customfield_11089',
                    'qtd_cobrada': 'customfield_11090',
                    'qtd_recebida': 'customfield_11091',
                    'kg_cobrada': 'customfield_11092', 
                    'kg_recebida': 'customfield_11093'
                }
            ]
            
            # Processar cada grupo
            for group_idx, group in enumerate(product_groups):
                produto = self.get_custom_field_value(fields, group['produto'])
                categoria = self.get_custom_field_value(fields, group['categoria'])
                
                # Debug dos produtos
                if produto or categoria:
                    logger.debug(f"Grupo {group_idx+1} - Produto: {produto}, Categoria: {categoria}")
                
                # Se há produto ou categoria, criar registro
                if produto or categoria:
                    products_found = True
                    record = base_record.copy()
                    record.update({
                        'Material': produto,
                        'Categoria': categoria,
                        'Quantidade Cobrada': self.get_custom_field_value(fields, group['qtd_cobrada']),
                        'Quantidade Recebida': self.get_custom_field_value(fields, group['qtd_recebida']),
                        'Quantidade de KG cobrada': self.get_custom_field_value(fields, group['kg_cobrada']),
                        'Quantidade de KG recebida': self.get_custom_field_value(fields, group['kg_recebida'])
                    })
                    processed.append(record)
            
            # Se nenhum produto foi encontrado, criar registro vazio
            if not products_found:
                record = base_record.copy()
                record.update({
                    'Material': '',
                    'Categoria': '',
                    'Quantidade Cobrada': '',
                    'Quantidade Recebida': '',
                    'Quantidade de KG cobrada': '',
                    'Quantidade de KG recebida': ''
                })
                processed.append(record)
            else:
                issues_with_products += 1
        
        logger.info(f"Processamento concluído: {len(processed)} registros de {len(issues)} issues")
        logger.info(f"Issues com produtos: {issues_with_products}")
        
        return processed
    
    def process_avarias(self, issues):
        logger.info(f"Processando {len(issues)} issues de avarias")
        processed = []
        
        for issue in issues:
            fields = issue.get('fields', {})
            
            record = {
                'Chave Log': issue.get('key', ''),
                'Status': fields.get('status', {}).get('name', ''),
                'Criado em': self.format_date(fields.get('created')),
                'Quem Criou': fields.get('reporter', {}).get('displayName', ''),
                'Loja': self.get_custom_field_value(fields, 'customfield_10169'),
                'Produto': self.get_custom_field_value(fields, 'customfield_11090'),
                'Quantidade': self.get_custom_field_value(fields, 'customfield_10315'),
                'Tipo de Avaria': self.get_custom_field_value(fields, 'customfield_11091'),
            }
            processed.append(record)
        
        logger.info(f"Avarias processadas: {len(processed)} registros")
        return processed
    
    def process_qualidade(self, issues):
        logger.info(f"Processando {len(issues)} issues de qualidade")
        processed = []
        
        for issue in issues:
            fields = issue.get('fields', {})
            
            record = {
                'Log': issue.get('key', ''),
                'Status': fields.get('status', {}).get('name', ''),
                'Criado em': self.format_date(fields.get('created')),
                'Quem Abriu': fields.get('reporter', {}).get('displayName', ''),
                'Loja': self.get_custom_field_value(fields, 'customfield_10169'),
                'Produto': self.get_custom_field_value(fields, 'customfield_11090'),
                'Quantidade': self.get_custom_field_value(fields, 'customfield_10315'),
                'Data Prox. Inventário': self.get_custom_field_value(fields, 'customfield_10475'),
            }
            processed.append(record)
        
        logger.info(f"Qualidade processada: {len(processed)} registros")
        return processed
    
    def process_devolucoes(self, issues):
        logger.info(f"Processando {len(issues)} issues de devoluções")
        processed = []
        
        for issue in issues:
            fields = issue.get('fields', {})
            
            record = {
                'Chave': issue.get('key', ''),
                'Status': fields.get('status', {}).get('name', ''),
                'Criado em': self.format_date(fields.get('created')),
                'Quem Abriu': fields.get('reporter', {}).get('displayName', ''),
                'Loja': self.get_custom_field_value(fields, 'customfield_10169'),
                'Tipo': self.get_custom_field_value(fields, 'customfield_11218'),
            }
            processed.append(record)
        
        logger.info(f"Devoluções processadas: {len(processed)} registros")
        return processed
    
    def get_custom_field_value(self, fields, field_id):
        """Extrai valor de custom field com debug"""
        field_value = fields.get(field_id)
        
        if field_value is None:
            return ''
        
        # Se é um objeto com 'value' ou 'name'
        if isinstance(field_value, dict):
            result = field_value.get('value', field_value.get('name', str(field_value)))
            return result
        
        # Se é uma lista
        elif isinstance(field_value, list) and field_value:
            first_item = field_value[0]
            if isinstance(first_item, dict):
                result = first_item.get('value', first_item.get('name', str(first_item)))
                return result
            return str(first_item)
        
        # Valor simples
        return str(field_value)
    
    def format_date(self, date_string):
        """Formata data para padrão brasileiro"""
        if not date_string:
            return ''
        
        try:
            if 'T' in str(date_string):
                dt = datetime.fromisoformat(str(date_string).replace('Z', '+00:00'))
                return dt.strftime('%d/%m/%Y')
            return str(date_string)
        except Exception as e:
            logger.warning(f"Erro ao formatar data {date_string}: {e}")
            return str(date_string)

    def get_divergencia_fields(self):
        """Retorna a lista de campos necessários para divergências"""
        return self.divergencia_fields