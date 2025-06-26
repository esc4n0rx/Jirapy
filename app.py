from flask import Flask, render_template, request, jsonify, send_file
import os
import pandas as pd
import requests
from datetime import datetime
import json
from dotenv import load_dotenv
import threading
from io import BytesIO

# Carregar variáveis de ambiente
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

class JiraService:
    def __init__(self):
        # Buscar credenciais das variáveis de ambiente
        self.email = os.getenv('JIRA_EMAIL')
        self.token = os.getenv('JIRA_TOKEN')
        
        if not self.email or not self.token:
            raise ValueError("JIRA_EMAIL e JIRA_TOKEN devem estar configurados no arquivo .env")
        
        self.session = requests.Session()
        self.session.auth = (self.email, self.token)
        self.session.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        self.max_results = 100
        
    def fetch_issues(self, jql, process_function):
        """Busca issues do Jira usando JQL"""
        url = f"https://hnt.atlassian.net/rest/api/2/search"
        data_to_save = []
        
        try:
            # Primeira requisição para obter o total
            params = {
                'jql': jql,
                'maxResults': self.max_results,
                'startAt': 0
            }
            
            response = self.session.get(url, params=params, verify=False)
            
            if response.status_code == 200:
                data = response.json()
                total_issues = data['total']
                pages = -(-total_issues // self.max_results)  # Ceiling division
                
                # Processar todas as páginas
                for page in range(pages):
                    params['startAt'] = page * self.max_results
                    response = self.session.get(url, params=params, verify=False)
                    
                    if response.status_code == 200:
                        issues = response.json()["issues"]
                        for issue in issues:
                            process_function(issue, data_to_save)
                
                return data_to_save, total_issues
            else:
                return None, f"Erro na requisição: {response.status_code} - Verifique as credenciais no .env"
                
        except Exception as e:
            return None, f"Erro: {str(e)}"
    
    def fetch_divergencias(self, start_date, end_date):
        """Busca divergências por período"""
        jql = f'project=LOG AND created>="{start_date}" AND created<="{end_date}"'
        data, result = self.fetch_issues(jql, self.process_divergencia_issue)
        
        if data:
            df = pd.DataFrame(data)
            df = self.reorganize_divergencias_data(df)
            return df.to_dict('records'), len(data)
        
        return None, result
    
    def fetch_avarias(self):
        """Busca avarias"""
        jql = 'project = LOG AND "Request Type" = "Informar avaria na entrega - Central de Produção" AND "Centro de Distribuição - Central de Produção" = RJ ORDER BY created DESC, priority DESC'
        data, result = self.fetch_issues(jql, self.process_avaria_issue)
        
        if data:
            return data, len(data)
        
        return None, result
    
    def fetch_qualidade(self):
        """Busca qualidade"""
        jql = 'project = LOG AND "Request Type" = "Qualidade (LOG)" AND "Centro de Distribuição - Central de Produção" = RJ ORDER BY priority ASC, "Tempo de resolução" ASC'
        data, result = self.fetch_issues(jql, self.process_qualidade_issue)
        
        if data:
            return data, len(data)
        
        return None, result
    
    def fetch_devolucoes(self):
        """Busca devoluções"""
        jql = 'project = LOG AND "Request Type" = "Devolução aos CDs por avarias de validade" AND "Centro de distribuição de destino (CD)" = "CD Pavuna RJ (CD03)" ORDER BY priority DESC, "Tempo de resolução" ASC'
        data, result = self.fetch_issues(jql, self.process_devolucao_issue)
        
        if data:
            return data, len(data)
        
        return None, result
    
    def process_divergencia_issue(self, issue, data_to_save):
        """Processa issue de divergência"""
        created_raw = issue["fields"].get("created", "")
        created_date = datetime.strptime(created_raw, '%Y-%m-%dT%H:%M:%S.%f%z').date() if created_raw else ""
        created_formatted = created_date.strftime('%d/%m/%Y') if created_date else ""

        custom_field_names = {
            # embalagem
            "customfield_11070": "EMBALAGEM 1", "customfield_11071": "EMBALAGEM 2",
            "customfield_11072": "EMBALAGEM 3", "customfield_11073": "EMBALAGEM 4",
            "customfield_11074": "EMBALAGEM 5",
            # flv
            "customfield_11075": "FLV 1", "customfield_11076": "FLV 2",
            "customfield_11077": "FLV 3", "customfield_11078": "FLV 4",
            "customfield_11079": "FLV 5",
            # mercearia
            "customfield_11080": "MERCEARIA 1", "customfield_11081": "MERCEARIA 2",
            "customfield_11082": "MERCEARIA 3", "customfield_11083": "MERCEARIA 4",
            "customfield_11084": "MERCEARIA 5",
            # pereciveis
            "customfield_11085": "PERECIVEIS 1", "customfield_11086": "PERECIVEIS 2",
            "customfield_11087": "PERECIVEIS 3", "customfield_11088": "PERECIVEIS 4",
            "customfield_11089": "PERECIVEIS 5",
            # produção
            "customfield_11090": "PRODUCAO 1", "customfield_11091": "PRODUCAO 2",
            "customfield_11092": "PRODUCAO 3", "customfield_11093": "PRODUCAO 4",
            "customfield_11094": "PRODUCAO 5",
        }

        basic_info = {
            "LOG": issue["key"],
            "Status": issue["fields"]["status"]["name"] if issue["fields"].get("status") else "",
            "Data de Criação": created_formatted,
            "Tipo de CD": self.safe_get_field_value(issue["fields"].get("customfield_10466")),
            "Tipo de Divergencia": self.safe_get_field_value(issue["fields"].get("customfield_10300")),
            "Data de Recebimento": self.safe_get_field_value(issue["fields"].get("customfield_10433")),
            "Loja": self.safe_get_field_value(issue["fields"].get("customfield_10169")),
        }

        # Adicionar campos de quantidade
        for i in range(1, 6):
            basic_info[f"Quantidade Nota Fiscal {i}"] = self.safe_get_field_value(issue["fields"].get(f"customfield_1031{4+i-1}"))
            basic_info[f"Quantidade Recebida {i}"] = self.safe_get_field_value(issue["fields"].get(f"customfield_1031{5+i-1}"))

        for cf_id, cf_name in custom_field_names.items():
            material_value = issue["fields"].get(cf_id)
            if material_value is not None:
                product_info = basic_info.copy()
                product_info.update({
                    "Categoria": cf_name,
                    "Material": self.safe_get_field_value(material_value)
                })
                data_to_save.append(product_info)
    
    def process_avaria_issue(self, issue, data_to_save):
        """Processa issue de avaria"""
        created_raw = issue["fields"].get("created", "")
        created_date = datetime.strptime(created_raw, '%Y-%m-%dT%H:%M:%S.%f%z').date() if created_raw else ""
        created_formatted = created_date.strftime('%d/%m/%Y') if created_date else ""
        
        # Processar produtos (até 5) - MUDANÇA: quebra de linha em vez de join
        produtos = []
        for i in range(90, 95):  # customfield_11090 a customfield_11094
            produto_field = issue["fields"].get(f"customfield_110{i}")
            if produto_field:
                produtos.append(self.safe_get_field_value(produto_field))
        
        # Cada produto em uma linha separada
        if produtos:
            for produto in produtos:
                avaria_info = {
                    "LOG": issue["key"],
                    "Data de Criação": created_formatted,
                    "Próximo Inventário": self.safe_get_field_value(issue["fields"].get("customfield_10475")),
                    "Quem Abriu": issue["fields"]["reporter"]["displayName"] if issue["fields"].get("reporter") else "",
                    "Email Criador": issue["fields"]["reporter"]["emailAddress"] if issue["fields"].get("reporter") else "",
                    "Loja": self.safe_get_field_value(issue["fields"].get("customfield_10169")),
                    "Produto": produto,
                    "Responsável": issue["fields"]["assignee"]["displayName"] if issue["fields"].get("assignee") else "",
                    "Email Responsável": issue["fields"]["assignee"]["emailAddress"] if issue["fields"].get("assignee") else "",
                    "Quantidade": self.safe_get_field_value(issue["fields"].get("customfield_10315")),
                    "Validade": self.safe_get_field_value(issue["fields"].get("customfield_10290")),
                    "Tipo de Avaria": self.safe_get_field_value(issue["fields"].get("customfield_10288")),
                    "Observações": self.safe_get_field_value(issue["fields"].get("customfield_12336")),
                }
                data_to_save.append(avaria_info)
        else:
            # Se não há produtos, ainda criar uma entrada
            avaria_info = {
                "LOG": issue["key"],
                "Data de Criação": created_formatted,
                "Próximo Inventário": self.safe_get_field_value(issue["fields"].get("customfield_10475")),
                "Quem Abriu": issue["fields"]["reporter"]["displayName"] if issue["fields"].get("reporter") else "",
                "Email Criador": issue["fields"]["reporter"]["emailAddress"] if issue["fields"].get("reporter") else "",
                "Loja": self.safe_get_field_value(issue["fields"].get("customfield_10169")),
                "Produto": "",
                "Responsável": issue["fields"]["assignee"]["displayName"] if issue["fields"].get("assignee") else "",
                "Email Responsável": issue["fields"]["assignee"]["emailAddress"] if issue["fields"].get("assignee") else "",
                "Quantidade": self.safe_get_field_value(issue["fields"].get("customfield_10315")),
                "Validade": self.safe_get_field_value(issue["fields"].get("customfield_10290")),
                "Tipo de Avaria": self.safe_get_field_value(issue["fields"].get("customfield_10288")),
                "Observações": self.safe_get_field_value(issue["fields"].get("customfield_12336")),
            }
            data_to_save.append(avaria_info)
    
    def process_qualidade_issue(self, issue, data_to_save):
        """Processa issue de qualidade"""
        created_raw = issue["fields"].get("created", "")
        created_date = datetime.strptime(created_raw, '%Y-%m-%dT%H:%M:%S.%f%z').date() if created_raw else ""
        created_formatted = created_date.strftime('%d/%m/%Y') if created_date else ""
        
        # Processar produtos (até 5)
        produtos = []
        for i in range(90, 95):  # customfield_11090 a customfield_11094
            produto_field = issue["fields"].get(f"customfield_110{i}")
            if produto_field:
                produtos.append(self.safe_get_field_value(produto_field))
        
        # Criar entrada para cada produto
        if produtos:
            for produto in produtos:
                qualidade_info = {
                    "LOG": issue["key"],
                    "Criado em": created_formatted,
                    "Status": issue["fields"]["status"]["name"] if issue["fields"].get("status") else "",
                    "Data Prox. Inventário": self.safe_get_field_value(issue["fields"].get("customfield_10475")),
                    "Quem Abriu": issue["fields"]["reporter"]["displayName"] if issue["fields"].get("reporter") else "",
                    "Loja": self.safe_get_field_value(issue["fields"].get("customfield_10169")),
                    "Produto": produto,
                    "Quantidade": self.safe_get_field_value(issue["fields"].get("customfield_10315")),
                }
                data_to_save.append(qualidade_info)
        else:
            qualidade_info = {
                "LOG": issue["key"],
                "Criado em": created_formatted,
                "Status": issue["fields"]["status"]["name"] if issue["fields"].get("status") else "",
                "Data Prox. Inventário": self.safe_get_field_value(issue["fields"].get("customfield_10475")),
                "Quem Abriu": issue["fields"]["reporter"]["displayName"] if issue["fields"].get("reporter") else "",
                "Loja": self.safe_get_field_value(issue["fields"].get("customfield_10169")),
                "Produto": "",
                "Quantidade": self.safe_get_field_value(issue["fields"].get("customfield_10315")),
            }
            data_to_save.append(qualidade_info)
    
    def process_devolucao_issue(self, issue, data_to_save):
        """Processa issue de devolução"""
        created_raw = issue["fields"].get("created", "")
        created_date = datetime.strptime(created_raw, '%Y-%m-%dT%H:%M:%S.%f%z').date() if created_raw else ""
        created_formatted = created_date.strftime('%d/%m/%Y') if created_date else ""
        
        devolucao_info = {
            "LOG": issue["key"],
            "Data de Criação": created_formatted,
            "Loja": self.safe_get_field_value(issue["fields"].get("customfield_10169")),
            "Tipo": self.safe_get_field_value(issue["fields"].get("customfield_11218")),
            "Quem Criou": issue["fields"]["reporter"]["displayName"] if issue["fields"].get("reporter") else "",
            "Email Criador": issue["fields"]["reporter"]["emailAddress"] if issue["fields"].get("reporter") else "",
            "Status": issue["fields"]["status"]["name"] if issue["fields"].get("status") else "",
        }
        
        data_to_save.append(devolucao_info)
    
    def safe_get_field_value(self, issue_field):
        """Obtem valor seguro do campo"""
        if isinstance(issue_field, dict):
            return issue_field.get('value', "")
        return issue_field if issue_field is not None else ""
    
    def reorganize_divergencias_data(self, df):
        """Reorganiza dados de divergências"""
        new_data = []
        
        for i in range(1, 6):
            df[f'Quantidade Nota Fiscal {i}'] = df[f'Quantidade Nota Fiscal {i}'].astype('object')
            df[f'Quantidade Recebida {i}'] = df[f'Quantidade Recebida {i}'].astype('object')
       
        for log in df['LOG'].unique():
            log_df = df[df['LOG'] == log]
            
            for i in range(1, 6):
                nf_column = f'Quantidade Nota Fiscal {i}'
                qr_column = f'Quantidade Recebida {i}'
                
                for index, row in log_df.iterrows():
                    if pd.notna(row[nf_column]) or pd.notna(row[qr_column]):
                        product_data = {
                            "LOG": row['LOG'],
                            "Status": row['Status'],
                            "Data de Criação": row['Data de Criação'],
                            "Tipo de CD": row['Tipo de CD'],
                            "Tipo de Divergência": row['Tipo de Divergencia'],
                            "Data de Recebimento": row['Data de Recebimento'],
                            "Loja": row['Loja'],
                            "Categoria": row['Categoria'],
                            "Material": row['Material'],
                            "Quantidade Cobrada": row[nf_column] if pd.notna(row[nf_column]) else "",
                            "Quantidade Recebida": row[qr_column] if pd.notna(row[qr_column]) else "",
                        }
                        new_data.append(product_data)

        return pd.DataFrame(new_data)

@app.route('/')
def index():
    # Verificar se as variáveis de ambiente estão configuradas
    jira_email = os.getenv('JIRA_EMAIL')
    jira_token = os.getenv('JIRA_TOKEN')
    
    config_status = {
        'email_configured': bool(jira_email),
        'token_configured': bool(jira_token),
        'email_preview': jira_email[:10] + '...' if jira_email and len(jira_email) > 10 else jira_email
    }
    
    return render_template('index.html', config=config_status)

@app.route('/fetch_data', methods=['POST'])
def fetch_data():
    try:
        data = request.json
        report_type = data.get('type')
        
        # Verificar se as credenciais estão configuradas
        if not os.getenv('JIRA_EMAIL') or not os.getenv('JIRA_TOKEN'):
            return jsonify({
                'success': False, 
                'message': 'Credenciais não configuradas. Verifique as variáveis JIRA_EMAIL e JIRA_TOKEN no arquivo .env'
            })
        
        try:
            jira_service = JiraService()
        except ValueError as e:
            return jsonify({'success': False, 'message': str(e)})
        
        if report_type == 'divergencias':
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            
            if not start_date or not end_date:
                return jsonify({'success': False, 'message': 'Datas de início e fim são obrigatórias'})
            
            result, count = jira_service.fetch_divergencias(start_date, end_date)
            
        elif report_type == 'avarias':
            result, count = jira_service.fetch_avarias()
            
        elif report_type == 'qualidade':
            result, count = jira_service.fetch_qualidade()
            
        elif report_type == 'devolucoes':
            result, count = jira_service.fetch_devolucoes()
            
        else:
            return jsonify({'success': False, 'message': 'Tipo de relatório inválido'})
        
        if result is None:
            return jsonify({'success': False, 'message': count})
        
        return jsonify({
            'success': True, 
            'data': result, 
            'count': count,
            'message': f'{count} registros encontrados'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro: {str(e)}'})

@app.route('/download_excel', methods=['POST'])
def download_excel():
    try:
        data = request.json
        records = data.get('data', [])
        filename = data.get('filename', 'export.xlsx')
        
        if not records:
            return jsonify({'success': False, 'message': 'Nenhum dado para exportar'})
        
        # Criar DataFrame e salvar em Excel
        df = pd.DataFrame(records)
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Dados')
        
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao gerar Excel: {str(e)}'})

if __name__ == '__main__':
    app.run(debug=True)