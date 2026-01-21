pieline{
    agent any

    environment {
        DOCKER_IMAGE = 'jenkinsdocker-flask-demoapp'
        DOCKER_IMAGE = 'flask-demo'
        PORT = '5000'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    docker.build(DOCKER_IMAGE)
                }
            }
        }

        stage('Run Docker Container') {
            steps {
                script {
                    docker.image(DOCKER_IMAGE).run("-d -p ${PORT}:${PORT}")
                }
            }
        }
    }
}